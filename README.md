# Concordance

[![CI](https://github.com/Mohsen-Allani/Concordance/actions/workflows/ci.yml/badge.svg)](https://github.com/Mohsen-Allani/Concordance/actions/workflows/ci.yml)

Automatic three-way matching of **purchase orders (BC)**, **delivery notes (BL)** and **invoices (Facture)**.

Concordance reads a PDF of scanned or digital commercial documents, extracts their content with a Vision-LLM, checks the arithmetic, compares the three documents line by line, and produces a report that tells a human exactly what does not match.

It was built for a Tunisian industrial client where this check was done by hand: slow, error-prone, and complicated by poor scans and supplier formats that never agree on field names.

## Features

- **Format-agnostic extraction.** A Vision-LLM (Gemini) goes from page image to structured JSON, so "supp", "supplier" or "fournisseur" all land in the same field.
- **Scan handling.** OpenCV deskew, denoise and contrast enhancement for low-quality scans. Native PDFs skip this step.
- **Arithmetic validation.** A constraint solver checks `qty x unit price`, discounts, VAT and totals. Tolerances are derived from each document's own printed precision, never hardcoded.
- **BC-anchored comparison.** The purchase order is the reference. Lines are matched by evidence (exact reference, then reference found in a description, then text similarity), and ambiguous matches are flagged instead of guessed.
- **Human in the loop.** Low-confidence results go to review. The operator can fix values, resolve ambiguities, reassign, merge or detach lines. Every revision replays the whole deterministic chain, so results stay reproducible.
- **Report and history.** PDF report per analysis, full history in PostgreSQL, web dashboard.

## How it works

```
PDF
 |  L0  ingestion        split and render pages (300 dpi)
 |  L1  detection        native text or scanned page
 |  L2  preprocessing    deskew, denoise, contrast (scans only)
 |  L3  classification   BC / BL / Facture / other, per page   [Vision-LLM]
 |  L4  grouping         pages -> documents, scope check
 |  L5  extraction       image -> structured JSON              [Vision-LLM]
 |  L6  normalization    canonical fields, Decimal amounts, dates
 |  L7  validation       arithmetic solver, confidence score
 |  L8  comparison       BC <-> BL, BC <-> Facture, per product
 |  L9  report + storage PDF report, PostgreSQL archive
 v
Web app: upload, dashboard, history, review, report download
```

Only L3 and L5 call the model. L6 to L9 are deterministic and can be replayed for free from the saved extraction. See [docs/architecture.md](docs/architecture.md).

## Quick start

Requirements: Python 3.11+, PostgreSQL 14+, a [Gemini API key](https://aistudio.google.com/apikey). WeasyPrint needs the Pango library for PDF reports (see [docs/operations.md](docs/operations.md) for your OS).

```bash
git clone https://github.com/Mohsen-Allani/Concordance.git
cd Concordance

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env               # then edit: DATABASE_URL, SECRET_KEY, GEMINI_API_KEY
alembic upgrade head               # create the database schema
concordance create-user "Your Name" you@example.com
concordance serve                  # http://127.0.0.1:8000
```

Generate a secret with `openssl rand -hex 32`.

### With Docker

```bash
cp .env.example .env               # set SECRET_KEY and GEMINI_API_KEY
docker compose up --build          # app on http://localhost:8000, PostgreSQL included
docker compose exec app concordance create-user "Your Name" you@example.com
```

## Command line

| Command | What it does | Calls the model |
|---|---|---|
| `concordance run [pdf ...]` | Full pipeline L0 to L9 (default input: `samples/*.pdf`) | yes |
| `concordance compare [folder ...]` | Replay L6 to L8 on saved extractions | no |
| `concordance report [folder ...]` | Regenerate PDF reports | no |
| `concordance revise <folder> [file.json]` | Replay the comparison under operator revisions | no |
| `concordance history [id]` | List stored analyses, or show one | no |
| `concordance create-user NAME EMAIL` | Create an account (password prompted) | no |
| `concordance serve` | Start the web application | no |

`concordance run --no-db` skips the database, so you can try the pipeline with only a Gemini key. Results are written to `data/outputs/<pdf name>/`.

## Configuration

All settings come from environment variables or a `.env` file at the project root. See [.env.example](.env.example).

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | web app, `run` with storage | PostgreSQL URL |
| `SECRET_KEY` | web app | Signs session tokens |
| `GEMINI_API_KEY` | `run`, uploads | Vision-LLM access |
| `GEMINI_MODEL` | no | Model name (default `gemini-3.1-flash-lite`) |
| `TOKEN_MINUTES` | no | Session lifetime, default 480 |
| `CONCORDANCE_DATA_DIR` | no | Output and upload location, default `./data` |
| `WEASYPRINT_DLL_DIR` | Windows | Folder with Pango DLLs |

## Development

```bash
make install     # editable install with dev tools
make test        # 119 tests, no external service needed
make lint        # ruff
```

Tests run on SQLite and a fake Gemini client, so they need neither PostgreSQL nor an API key. Migration tests run against a real PostgreSQL when `TEST_POSTGRES_URL` is set (CI does this). See [CONTRIBUTING.md](CONTRIBUTING.md).

Optional semantic veto in L8 (multilingual embeddings, heavy download):

```bash
pip install -e ".[semantic]"
```

## Project layout

```
src/concordance/
  stages/        L0-L6  ingestion, detection, preprocessing, classification,
                        grouping, extraction, normalization
  validation/    L7     solver, tolerance, scoring, certification
  comparison/    L8     matching engine, operator overrides
  reporting/     L9     Jinja2 + WeasyPrint report
  db/            L9     SQLAlchemy models and persistence
  webapp/               FastAPI routes and static frontend
  schemas/              JSON schemas sent to the Vision-LLM
  pipeline.py           orchestration of L0 to L9
  replay.py             free replay of L6 to L9
  cli.py                the `concordance` command
migrations/             Alembic migrations
tests/                  pytest suite
docs/                   architecture, API, operations
samples/                one synthetic demo PDF
```

## Documentation

- [Architecture](docs/architecture.md): layers, design principles, current gaps
- [API reference](docs/api.md): endpoints and the revision format
- [Operations](docs/operations.md): installation per OS, PostgreSQL, WeasyPrint, security notes

## Privacy

Documents are business records. Keep real supplier documents out of the repository: `data/` and `samples/private/` are git-ignored.
