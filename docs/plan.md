# Market Leads Platform — Plan

_Last updated: 2026-08-26_

## Vision

An internal web tool for our market leads to assemble supplier orders and track
performance. Built in phases; the first deliverable is a searchable database of
historical supplier price lists.

## Confirmed context

- **Supplier:** Van-Whole Produce (Vancouver, BC). Single supplier for now.
- **Price list format:** PDF only. Digital (text layer present), ~9 pages,
  ~800–1,000 SKUs per list, issued roughly twice weekly (3-day effective range
  in the header, e.g. "Aug 24 - 26, 2026").
- **Email delivery:** lands in individual inboxes today; no shared mailbox.
- **Users:** small internal team (market leads). Google Workspace shop.

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React + TypeScript on Vercel | Vite SPA to start; Next.js only if SSR/BFF needed |
| Backend | Go, container on Google Cloud Run | Scales to zero; clean cron/workers. Fly.io is the alt |
| Database | Neon Postgres | Use branching for preview envs. No large files in Postgres |
| Blob storage | Cloudflare R2 (or Vercel Blob) | Raw price-list PDFs live here; DB stores metadata + refs |
| Auth | Google OAuth restricted to Workspace domain | Auth.js on web, verify session in Go |
| Repo | Monorepo: `/web`, `/api` (Go), `/pricelistparser` (Python), `/db`, `/docs` | |
| DB tooling | `goose` or Atlas migrations, `sqlc` typed queries | |

## Ingestion strategy (price lists)

Build in order:

1. **Manual upload** — drag a PDF in, set received/effective dates. Always-on fallback.
2. **Dedicated forwarding address** — e.g. `pricelists@…` via Cloudflare Email
   Routing / Postmark inbound → webhook → auto-draft. Leads forward supplier emails.
3. **Historical backfill** — whoever has the deepest mail history does a Gmail
   search (`from:van-whole has:attachment filename:pdf`) and forwards in batches
   to the same address. Likely a one-time ~20-minute job for one supplier.

Per-user Gmail API OAuth is not worth it at this scale.

## PDF parsing — hybrid approach

The Van-Whole PDF is a rigid two-column grid: each row is `DESCRIPTION … PRICE`,
prices right-aligned to x≈302 (left col) and x≈590 (right col), column gutter at
x≈306. Section headers are letter-spaced bold caps (`F R U I T S`,
`S A L A D - T A Y L O R F A R M`). No OCR needed.

- **Raw extraction (BUILD FIRST).** Python + pdfplumber.
  Coordinate-based: drop header/footer y-band, split page at x≈306, cluster
  words into rows by y, right-aligned `\d+\.\d2|N/A` token is the price, rest is
  the description, track current section header. Output: raw rows as JSON.
- **Enrichment (LATER).** LLM (Claude API) or rules: split each
  `description` into `commodity, variety, grade, origin, pack_count, pack_size,
  unit, price_basis, organic, brand, day_available, promo, limited,
  supplier_sku`. Cache by exact description string — recurring SKUs enrich once.
- **Validation + review UI.** Row-count reconciliation per page, price
  sanity, % change vs previous list. Failures land the list in "needs review",
  never block.

### Status (2026-08-26)

Raw extraction is built and working (`pricelistparser/`, Python + pdfplumber).
Verified against the real Aug 24-26 sample: 717 rows, 0 warnings. Tooling runs
on **uv + Python 3.14** (`pricelistparser/.python-version`, `uv.lock`, `uv_build`
backend); CI uses `astral-sh/setup-uv`.

**Fixture decision resolved:** repo is public; the real PDF is never committed.
Instead `pricelistparser/tests/fixtures/van_whole/synthetic.pdf` is a generated
stand-in — same page size, column geometry, letterhead strings, and
letter-spaced headers as the real format (so it exercises `van_whole.py`
exactly as shipped), but every product/price/code is fabricated. Built by
`generate_synthetic.py` (reportlab), deliberately covering every known format
quirk below (organic-section prefixing, `PER LB` basis, `N/A` rows, embedded
SKU codes, the orphan-price-merge case, an unknown-section warning, per-column
running-section reset). This is the committed golden fixture; a real PDF may
still be dropped in the same directory for local-only testing (gitignored).

18 tests pass (golden output match, edge-case assertions, sniff confidence,
structural invariants, helper unit tests), ruff clean.

Not yet done: DB schema, Go ingestion, review UI, enrichment, pushing to
GitHub (repo will be public, remote not yet created).

### Language decision

- Webhook + orchestration + DB writes: **Go**.
- Raw extraction: **Python (pdfplumber)** — Go's PDF libraries are weak
  (fragile pure-Go, or commercial/AGPL, or no extraction API), and pdfplumber's
  `extract_words()` + visual debugging make tuning much faster.
- Webhook responds fast and enqueues a job; the parser runs async, so
  co-locating buys little. Start: Go invokes the Python CLI as a subprocess.
  Later: promote parser to its own Cloud Run service over the same JSON contract.

### Parser I/O contract

```
IN:  PDF path/bytes  (+ optional supplier slug; auto-detected via sniff() when omitted)
OUT: {
  meta: { supplier, parser_key, parser_version, contract_version, currency,
          effective_from, effective_to, issued_date, page_count, data_pages,
          sha256, source_filename, row_count },
  rows: [ { page, column, section, description, price_raw, price,
            unavailable, price_basis, supplier_sku, bbox, source_line } ],
  warnings: [ { code, detail, page } ]
}
```

Parser is stateless, never touches Neon. `contract_version` is bumped on any
breaking change to these field names; `parser_version` on any change that alters
a given supplier's output. Tested with golden `input.pdf → expected.json` pairs.

### Multi-supplier structure

- `pricelistparser/src/pricelistparser/suppliers/<slug>.py` — one module per
  supplier, each a `SupplierParser` (`slug`, `key`, `version`, `sniff()`,
  `parse()`), registered in `dispatch.REGISTRY`.
- `pricelistparser/src/pricelistparser/lib/` — shared geometry/text helpers
  (column split, row clustering, orphan-price merge, price detection, section
  normalization).
- Supplier is chosen explicitly at ingest (email From-address → supplier map, or
  manual pick); `dispatch.detect()` runs `sniff()` as a cross-check and the
  runner emits `low_sniff_confidence` when the pick disagrees with the PDF.
- DB: `supplier_email_senders` (routing), `supplier_vocab` (per-supplier tag
  meanings); `price_lists` records `parser_key` + `parser_version`.

### Known format challenges

- Two-column interleave in linear text → split at x≈306.
- Header/footer noise (address, phone, "PRICE SUBJECT TO CHANGE", page number) → y-band + string denylist.
- Section headers letter-spaced → detect by 1-char tokens / bold font; collapse spaces.
- Effective date is a range in the header → regex to `effective_from`/`effective_to`.
- Page 1 is a decorative "New / Seasonal Items" cover → skip for pricing.
- `N/A` prices → keep row, null price, `status = unavailable`.
- `PER LB` items → `price_basis = lb` not `case`.
- Embedded codes `(11196)`, `4510097`, `(30002474)` → capture as `supplier_sku`.
- Long descriptions bump the price to a sub-line ~2px down → merge adjacent price-only + description-only rows.
- Parenthetical tags `(ORG)(BK)(THUR)(TF)(F. EXP.)(DRISCOLL)(PROMO)(LTD)` →
  tag lookup table; seed it, extend via review UI. `(BK)` meaning TBC.
- Same commodity in Organic and Conventional sections → identity = verbatim description + section.

## Conceptual data model

- `suppliers`
- `source_documents` — supplier_id, received_at, email_from/subject, file_url, sha256, ingest_method, status
- `price_lists` — source_document_id, effective_from, effective_to, issued_date, currency, status (draft/approved), approved_by
- `price_list_rows` — price_list_id, page, column, section, description (verbatim), price_raw, price, unavailable, price_basis, supplier_sku, review_state, + (later) enriched fields, matched_product_id
- `products` — canonical name, category, base_uom  _(later)_
- `product_aliases` — supplier_id, alias_text, product_id  _(later)_
- `prices` — product_id, supplier_id, price, currency, uom, effective_from, effective_to, price_list_row_id  _(later)_
- `users`

## Milestones

- **Spike** — gather 8–10 historical PDFs, assess layout variance. _(pending: need historical samples)_
- **M0** — monorepo scaffold, Neon + Cloud Run + Vercel wired, Google-domain auth, hello-world deploy.
- **M1 (current focus)** — ~~raw-extraction parser~~ (done) + schema + Go ingestion +
  manual PDF upload → `price_list_rows` in Postgres; document archive with
  list/detail + raw file view.
- **M1.5** — dedicated forwarding address → inbound webhook → auto-draft.
- **M2** — enrichment + description field parsing.
- **M3** — review UI; product catalog + alias mapping; commit to normalized price history.
- **M4** — price-history trend view + price-list diff ("what changed since last list").
- **M5** — backfill full history; harden parser against the whole corpus.
- **M6** — order building against the current price book.
- **M7** — performance dashboards _(metrics still to be defined)_.

## Open questions

- What should "tracking performance" measure — margin, order volume, price variance, win rate?
- How far back does the price-list history go? How many files total?
- Single currency (CAD) always?
- Meaning of the `(BK)` tag and other unconfirmed parenthetical codes.
