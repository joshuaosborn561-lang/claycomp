from __future__ import annotations

import asyncio
import os
from typing import Sequence

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from claycomp.enrichers.base import Enricher
from claycomp.models import Record

console = Console()


async def _enrich_one(enricher: Enricher, record: Record, semaphore: asyncio.Semaphore) -> None:
    async with semaphore:
        try:
            result = await enricher.enrich(record)
            record.set_enriched(enricher.output_column(), result.value)
        except Exception as e:
            record.set_enriched(enricher.output_column(), None)
            record.set_enriched(f"{enricher.output_column()}_error", str(e))


async def run_pipeline(
    records: list[Record],
    enrichers: Sequence[Enricher],
    *,
    concurrency: int = 5,
    show_progress: bool = True,
) -> list[Record]:
    """Run enrichers sequentially per record, with parallel records."""

    missing_keys = {
        e.requires_api_key
        for e in enrichers
        if e.requires_api_key and not os.getenv(e.requires_api_key)
    }
    if missing_keys:
        console.print(
            f"[yellow]Warning: missing API keys {missing_keys} — "
            f"some enrichers will return placeholders[/yellow]"
        )

    semaphore = asyncio.Semaphore(concurrency)

    for enricher in enrichers:
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"[cyan]{enricher.name}[/cyan]", total=len(records))
                tasks = []

                async def run_with_progress(rec: Record) -> None:
                    await _enrich_one(enricher, rec, semaphore)
                    progress.advance(task)

                for record in records:
                    tasks.append(asyncio.create_task(run_with_progress(record)))
                await asyncio.gather(*tasks)
        else:
            await asyncio.gather(
                *[_enrich_one(enricher, r, semaphore) for r in records]
            )

    return records
