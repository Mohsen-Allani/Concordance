# Contributing

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install        # optional
```

## Before opening a pull request

```bash
make lint
make test
```

Tests need no API key and no PostgreSQL. To also run the migration tests, start a PostgreSQL and set `TEST_POSTGRES_URL` (see `tests/test_migrations.py`).

## Conventions

- Layers are strictly ordered (L0 to L9). A layer reads only its predecessor's output.
- Anything after L5 must stay deterministic. Do not add a model call or randomness there.
- Do not hardcode tolerances or thresholds tied to sample documents. Derive them from the document.
- A bug fix comes with a test that fails without it.
- Schema changes to `db/models.py` need an Alembic migration.
- Never commit real documents, `.env` files or anything under `data/`.
- The domain vocabulary is French (BC, BL, Facture, remise, matricule fiscal) and is kept as is in code and UI. Documentation is in English.
