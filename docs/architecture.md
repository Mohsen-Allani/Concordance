# Architecture

## Overview

Concordance is a layered pipeline. Each layer takes the previous layer's output and adds one kind of knowledge. Only two layers use a model, which keeps cost and non-determinism confined.

| Layer | Module | Role | Deterministic |
|---|---|---|---|
| L0 | `stages/ingestion.py` | Split PDF, render pages at 300 dpi, count text characters | yes |
| L1 | `stages/detection.py` | Native text page or scanned page (character threshold) | yes |
| L2 | `stages/preprocessing.py` | Deskew, denoise, contrast, scans only | yes |
| L3 | `stages/classification.py` | Page type: BC, BL, Facture or other | no (model) |
| L4 | `stages/grouping.py` | Merge consecutive pages into documents, check scope | yes |
| L5 | `stages/extraction.py` | Page images to structured JSON using a response schema | no (model) |
| L6 | `stages/normalization.py` | Canonical field names, Decimal amounts, ISO dates, raw strings kept | yes |
| L7 | `validation/` | Arithmetic solver, discount propagation, certification, confidence | yes |
| L8 | `comparison/` | BC-anchored three-way matching | yes |
| L9 | `reporting/`, `db/` | PDF report and PostgreSQL archive | yes |

`pipeline.py` orchestrates L0 to L9 and writes each intermediate result under `data/outputs/<pdf>/`. `replay.py` re-runs L6 to L9 from those files without calling the model.

## Design principles

- **Extraction is the only expensive step.** Its raw output is archived (JSONB in the database, JSON on disk). Everything after it can be replayed at no cost on identical input.
- **Revisions are constraints, not edits.** An operator correction never patches an output. It is injected before matching and the chain is replayed in full, so the same documents and revisions always give the same verdict.
- **Tolerances come from the document.** Absolute thresholds break when amounts change scale. L7 infers the quantum from the printed decimals (Tunisian dinars use three) and the arithmetic structure.
- **The BC is the reference.** Every comparison is BC to BL and BC to Facture, never BL to Facture.
- **Evidence hierarchy for matching.** Exact reference, then a code found inside a description, then text similarity. Identifier strength is based on rarity (how many lines carry a code), not on length.
- **Ambiguity is not consumed.** An ambiguous match does not use up its candidates. When the operator resolves it, the pair is locked before matching reruns.
- **Semantic similarity is only a veto.** Embeddings can reject a text-level match, never override a code match. The dependency is optional and its absence is silent.
- **Fail visibly.** Low-confidence results are routed to human review. Reports are written atomically and validated (`%PDF-` header, `%%EOF` trailer) so a truncated file is never served.
- **Schemas are functional, not example-driven.** Field descriptions given to the model describe a field's role, to avoid overfitting to sample documents.

## Data model

Six tables (see `src/concordance/db/models.py`): users, analyses, documents, product lines, results, reports.

- Monetary amounts are `NUMERIC`, never float.
- Raw extraction, validation and comparison are stored as JSONB for audit and replay (JSON on SQLite, used for tests only).
- Operator revisions are archived on the analysis as an audit trail.

## Web application

FastAPI serves a JSON API under `/api` and a vanilla JS single page frontend under `/static`. Authentication is OAuth2 password flow with JWT. Uploads are processed in a FastAPI background task; the client polls a job endpoint for progress. Job state is held in memory and is lost on restart, while analyses are durable in the database. See [api.md](api.md).

## Known gaps and decisions to make

These are deliberate, documented differences from the original design document.

- **Frontend framework.** The design document shows React and Vite. The implementation is vanilla JS and HTML/CSS. Either build the React frontend or record the choice under "alternatives rejected".
- **pgvector.** Listed in the design document but unused. The semantic gate is a pairwise veto computed in process, not a similarity search, so pgvector adds nothing. Remove it from the document.
- **Model abstraction.** `stages/classification.py` and `stages/extraction.py` call the Gemini SDK directly. A thin provider interface would make the Qwen3-VL production path concrete.
- **Access control.** Any authenticated user can read every analysis. This matches an internal shared-history tool. Per-user or per-role scoping would be a small change in `webapp/analyses.py`.
- **Dashboard scalability.** `/api/stats` loads analyses in memory. Fine for hundreds, to be replaced by SQL aggregates for thousands.
- **Concurrency.** Job progress lives in process memory, so the application must run as a single worker. Several workers would need a shared job store or a task queue.
