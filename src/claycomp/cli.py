from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from claycomp.agents.enrichment_agent import EnrichmentAgent
from claycomp.enrichers import DEFAULT_PIPELINE, ENRICHERS, get_enrichers
from claycomp.io import load_csv, save_csv
from claycomp.models import Record
from claycomp.pipeline import run_pipeline

load_dotenv()

app = typer.Typer(
    name="claycomp",
    help="AI-powered lead enrichment — import Apollo CSVs, enrich, export.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def enrich(
    input: Path = typer.Argument(..., help="Input CSV (Apollo export)"),
    output: Path = typer.Option(Path("output/enriched.csv"), "--output", "-o"),
    columns: str = typer.Option(
        ",".join(DEFAULT_PIPELINE),
        "--columns", "-c",
        help=f"Comma-separated enrichers: {', '.join(ENRICHERS)}",
    ),
    limit: int = typer.Option(0, "--limit", "-n", help="Max rows to process (0 = all)"),
    concurrency: int = typer.Option(5, "--concurrency", help="Parallel row processing"),
):
    """Run enrichment pipeline on a CSV."""
    enricher_names = [c.strip() for c in columns.split(",") if c.strip()]
    enrichers = get_enrichers(enricher_names)

    console.print(f"[bold]Loading[/bold] {input}")
    records = load_csv(input)
    if limit > 0:
        records = records[:limit]

    console.print(f"[bold]Enriching[/bold] {len(records)} records with: {', '.join(enricher_names)}")
    asyncio.run(run_pipeline(records, enrichers, concurrency=concurrency))

    save_csv(records, output)
    console.print(f"[green]✓[/green] Saved to {output}")


@app.command()
def agent(
    input: Path = typer.Argument(..., help="Input CSV"),
    prompt: str = typer.Option(..., "--prompt", "-p", help="What to research for each lead"),
    output: Path = typer.Option(Path("output/agent_enriched.csv"), "--output", "-o"),
    column: str = typer.Option("agent_result", "--column", help="Output column name"),
    limit: int = typer.Option(0, "--limit", "-n"),
):
    """Run a custom AI agent prompt on each row."""
    records = load_csv(input)
    if limit > 0:
        records = records[:limit]

    agent_runner = EnrichmentAgent(prompt=prompt, output_column=column)
    console.print(f"[bold]Running agent[/bold] on {len(records)} records")
    console.print(f"[dim]Prompt: {prompt}[/dim]")

    async def run_all():
        for i, record in enumerate(records):
            result = await agent_runner.enrich(record)
            for key, val in result.items():
                record.set_enriched(key, val)
            console.print(f"  [{i+1}/{len(records)}] {record.display_name()}")

    asyncio.run(run_all())
    save_csv(records, output)
    console.print(f"[green]✓[/green] Saved to {output}")


@app.command()
def preview(
    input: Path = typer.Argument(..., help="Input CSV"),
    rows: int = typer.Option(5, "--rows", "-n"),
):
    """Preview loaded records."""
    records = load_csv(input)
    table = Table(title=f"Preview ({min(rows, len(records))} of {len(records)} rows)")
    table.add_column("Name")
    table.add_column("Email")
    table.add_column("Company")
    table.add_column("Location")

    for r in records[:rows]:
        table.add_row(r.display_name(), r.email or "—", r.company or "—", r.display_location() or "—")

    console.print(table)


@app.command(name="list")
def list_enrichers():
    """List available enrichment columns."""
    table = Table(title="Available Enrichers")
    table.add_column("Key")
    table.add_column("Output Column")
    table.add_column("Description")
    table.add_column("API Key")

    for key, cls in ENRICHERS.items():
        e = cls()
        table.add_row(key, e.name, e.description, e.requires_api_key or "—")

    console.print(table)


@app.command()
def sample():
    """Print sample Apollo-style CSV format."""
    sample_path = Path(__file__).parent / "data" / "sample_leads.csv"
    console.print(sample_path.read_text())


if __name__ == "__main__":
    app()
