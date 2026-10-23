# community-market-workbench

Internal platform for market leads to assemble supplier orders and track
performance. See [docs/plan.md](docs/plan.md) for the full plan and roadmap.

**Status:** early. Building M1 — the supplier price-list parsing layer
(raw PDF → Postgres).

## Licensing

No licence yet — all rights reserved. This code is not currently open source;
a licence may be added later.

## Layout

| Path | What |
|---|---|
| `pricelistparser/` | Python. Raw extraction of supplier price-list PDFs. Stateless, emits JSON. |
| `db/` | SQL migrations (goose). |
| `api/` | Go. Webhook, ingest orchestration, persistence, review API. |
| `web/` | React + TypeScript frontend (later). |
| `docs/` | Plan and design notes. |

## Architecture (M1)

```
inbound email / manual upload
      │  (Go: verify, store raw PDF in blob, resolve supplier, enqueue)
      ▼
pricelistparser/ raw extraction  ── per-supplier module, supplier-neutral JSON contract
      ▼
Go: validate ─► persist price_lists + price_list_rows (draft) in Postgres
      ▼
review UI ─► approve ─► normalized price history   (later milestones)
```

Only raw extraction and each supplier's tag vocabulary are supplier-specific;
the rest of the pipeline is shared.

## Local development

Requires [uv](https://docs.astral.sh/uv/) (manages the Python interpreter itself —
no separate Python install needed), Go 1.22+, Docker (for local Postgres).

```bash
# Parser (uv reads pricelistparser/.python-version and fetches 3.14 automatically)
cd pricelistparser
uv sync
uv run pytest

# Run raw extraction on a PDF
uv run pricelistparser path/to/pricelist.pdf --supplier van_whole --pretty
```

Copy `.env.example` to `.env` for local config. Never commit `.env`.
