# Operations

## Installation by platform

### System library for PDF reports

WeasyPrint renders reports with Pango. Without it, analyses still complete and the report step reports a clear error.

- **Debian / Ubuntu**: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0`
- **macOS**: `brew install pango`
- **Windows**: install [MSYS2](https://www.msys2.org), then in its shell run `pacman -S mingw-w64-x86_64-pango`. The default folder `C:\msys64\mingw64\bin` is detected automatically; for another location set `WEASYPRINT_DLL_DIR` in `.env`.
- **Docker**: handled by the provided `Dockerfile`.

### PostgreSQL

Create a database and a user, then put the URL in `.env`:

```sql
CREATE USER concordance WITH PASSWORD 'change-me';
CREATE DATABASE concordance OWNER concordance;
```

```
DATABASE_URL=postgresql+psycopg://concordance:change-me@localhost:5432/concordance
```

Apply the schema with `alembic upgrade head`. Special characters in the password must be URL-encoded (`@` becomes `%40`).

### Python environment

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

With conda: `conda create -n concordance python=3.12 && conda activate concordance && pip install -e ".[dev]"`.

## Migrations

```bash
alembic upgrade head                           # apply
alembic revision --autogenerate -m "message"   # after changing db/models.py
alembic downgrade -1                           # roll back one step
```

CI checks that the migrations produce exactly the schema described by the models.

## Data and backups

Everything written at runtime lives in `data/` (or `CONCORDANCE_DATA_DIR`): `outputs/` holds one folder per analysis, `uploads/` the submitted PDFs. Back it up together with the database. Report paths stored in the database are relative to the project root.

## Security notes

- Passwords are hashed with bcrypt; sessions are signed JWTs. Set a long random `SECRET_KEY` and never commit `.env`.
- There is no public sign-up. Accounts are created with `concordance create-user`.
- Run behind HTTPS (a reverse proxy such as Caddy or nginx) outside a trusted network.
- The frontend loads its fonts from Google Fonts. For a fully offline deployment, self-host Manrope and JetBrains Mono.
- Uploaded documents and extracted data are business records. Restrict access to `data/` and the database accordingly.
