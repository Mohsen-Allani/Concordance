# Changelog

## 1.0.0 - 2026-11-23

Repository rebuilt from the latest project version.

### Changed
- `src` layout with an installable `concordance` package and a single `concordance` command (`run`, `compare`, `report`, `revise`, `history`, `create-user`, `serve`).
- Pipeline stages grouped under `concordance.stages`; JSON schemas shipped inside the package.
- All configuration through environment variables or `.env`; the Windows MSYS2 path is no longer hardcoded.
- Database engine created on first use, so importing the package needs no database.
- `PyMuPDF` imported as `pymupdf`; `opencv-python-headless` replaces `opencv-python`.
- Alembic folder renamed `migrations/` to avoid shadowing the `alembic` library.

### Fixed
- HTML escaping was disabled in the PDF report template (`select_autoescape` did not match `.html.j2`), so text read from a document could inject markup. Escaping is now always on.
- Page image paths were stored relative to the project root but read relative to the current directory, so the pipeline failed unless started from the root.
- Alembic failed on database passwords containing `%`.
- Password hashing no longer depends on `passlib`, which breaks with recent `bcrypt` releases. Existing hashes remain valid.
- Login timing no longer reveals whether an e-mail exists.

### Added
- Test suite (119 tests): engine, validation, normalization, auth, API, CLI, report, and a full pipeline run with a fake Gemini client. Migration tests against PostgreSQL.
- `GET /api/health`, `concordance run --no-db`.
- Dockerfile, Docker Compose, GitHub Actions CI, Dependabot, pre-commit, Makefile.
- Documentation: README, architecture, API, operations.

### Removed
- Two sample PDFs that were scans of real supplier invoices. `samples/native_sample.pdf` (synthetic) remains.
