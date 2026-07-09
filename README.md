# Claycomp

AI-powered lead enrichment — a lightweight Clay alternative. Import Apollo CSVs, run enrichment columns, export personalized data for cold outreach.

## What it does

Drop in a lead list and enrich each row with:

| Enricher | Output | How |
|----------|--------|-----|
| `name` | `normalized_first_name` | AI normalizes "Robert" → "Rob" |
| `area` | `area_nickname` | AI finds "the Bay Area", "ATX", etc. |
| `baseball` | `nearest_baseball_team` | Geocode + nearest MLB team |
| `restaurant` | `nearest_nice_restaurant` | Google Places (top-rated nearby) |
| `review` | `company_google_review` | Google rating snippet for their company |

Plus a flexible **AI agent** for custom prompts like "find their local NBA team" or "suggest a personalized opener."

## Web UI

Claycomp has two modes — switch with the toggle in the header:

| Mode | Vibe | Best for |
|------|------|----------|
| **Table** | Clay-style spreadsheet with AI enrichment columns | Import CSV, add columns, run enrichments, export |
| **Chat** | ChatGPT-style assistant | Natural language: "enrich all with baseball teams", ask for openers |
| **Sculptor** | Clay-style co-pilot (in Table mode) | Describe enrichments in plain English, get column proposals, sandbox test before applying |

Switch AI provider (OpenAI, Perplexity, Anthropic) via the **settings** button in the header.

```bash
# Build frontend + start server
cd frontend && npm install && npm run build && cd ..
claycomp serve

# Open http://localhost:8000
```

For frontend development with hot reload:

```bash
# Terminal 1
claycomp serve

# Terminal 2
cd frontend && npm run dev   # proxies /api → :8000, UI at :5173
```

## Deploy to Vercel

Full UI + API on Vercel (serverless Python for `/api/*`, static React for everything else).

```bash
# 1. Install Vercel CLI and log in (opens browser)
npm i -g vercel
vercel login

# 2. From repo root — first deploy walks you through linking the project
vercel

# 3. Add environment variables in Vercel dashboard (Settings → Environment Variables)
#    OPENAI_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, GOOGLE_PLACES_API_KEY

# 4. Production deploy
vercel --prod
```

Or use the npm shortcuts from repo root:

```bash
npm run vercel:login
npm run vercel:deploy
```

**Notes:**
- API keys go in the Vercel project settings, not in the repo
- Serverless functions have a 60s timeout (enrichment of large lists may need smaller batches)
- Baseball enricher works without API keys; AI features need `OPENAI_API_KEY` (or another provider)

## Quick start (CLI)

```bash
# Install
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Configure API keys
cp .env.example .env
# Add OPENAI_API_KEY (required for name/area/agent)
# Add GOOGLE_PLACES_API_KEY (optional, for restaurant/review)

# Preview your CSV
claycomp preview src/claycomp/data/sample_leads.csv

# Run default enrichment pipeline
claycomp enrich src/claycomp/data/sample_leads.csv -o output/enriched.csv

# Run specific columns only
claycomp enrich leads.csv -c name,baseball,area -n 10

# Custom AI agent per row
claycomp agent leads.csv -p "Find the nearest NFL team and a fun fact about their stadium" -n 5

# List all enrichers
claycomp list
```

## Apollo export workflow

1. Export leads from Apollo (or ZoomInfo, LinkedIn Sales Nav, etc.) as CSV
2. Make sure you have at minimum: `email`, `first_name`, `city`/`state` (or `location`), `company`
3. Run `claycomp enrich your_export.csv`
4. Open `output/enriched.csv` — original columns plus `enriched_*` columns

Column names are auto-mapped from common Apollo headers (`organization_name` → `company`, etc.).

## Architecture

```
CSV in → Record[] → Enricher pipeline → CSV out
                      ├── NameNormalizer (OpenAI)
                      ├── AreaNickname (OpenAI)
                      ├── BaseballTeam (geocode + MLB dataset)
                      ├── Restaurant (Google Places)
                      ├── GoogleReview (Google Places)
                      └── EnrichmentAgent (custom OpenAI agent)
```

Each enricher is a pluggable class. Add your own in `src/claycomp/enrichers/`.

## Adding a custom enricher

```python
# src/claycomp/enrichers/my_enricher.py
from claycomp.enrichers.base import Enricher
from claycomp.models import EnrichmentResult, Record

class MyEnricher(Enricher):
    name = "my_column"
    description = "Does something cool"

    async def enrich(self, record: Record) -> EnrichmentResult:
        # your logic here
        return EnrichmentResult(column=self.name, value="result", source="my_api")
```

Register it in `src/claycomp/enrichers/__init__.py` and run with `-c my_key`.

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | For AI enrichers | Name normalization, area nicknames, Sculptor, Chat |
| `PERPLEXITY_API_KEY` | Optional | Use Perplexity as AI provider (web search capable) |
| `ANTHROPIC_API_KEY` | Optional | Use Claude as AI provider |
| `GOOGLE_PLACES_API_KEY` | Optional | Restaurant + company review lookups |
| `LLM_PROVIDER` | Optional | Default provider: `openai`, `perplexity`, or `anthropic` |
| `OPENAI_MODEL` / `PERPLEXITY_MODEL` / `ANTHROPIC_MODEL` | Optional | Override default model per provider |

## What's next

Ideas to vibe-code from here:

- **Waterfall enrichers** — try Clearbit, then Apollo, then scrape
- **Email opener generator** — combine enrichments into a draft line
- **Caching layer** — don't re-geocode the same city 500 times
- **More data sources** — Yelp, sports APIs, weather, local events
- **Batch scheduling** — cron job that picks up new CSVs from a folder

## License

MIT
