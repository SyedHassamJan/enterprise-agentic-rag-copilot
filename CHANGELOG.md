# Changelog

All notable changes. Versions follow [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-10-18

### Added
- Redesigned UI: a paper-and-ink internal-tool layout, Q&A with numbered footnotes linked to sources, a decision-trace timeline with per-step timing, a "viewing as" user switcher, an upload dialog, dark mode and a responsive layout.
- `GET /api/ready` readiness probe. `/api/health` now reports the version and environment.
- Docker: a multi-stage, non-root image with a `HEALTHCHECK` and a `/app/var` volume; `docker-compose.yml`; `.gitattributes` for LF line endings.
- GitHub Actions: CI (ruff, pytest on Python 3.11 and 3.12, Docker build + smoke test), Release (GHCR publish + deploy hook), and Evaluation (LLM quality gate); Dependabot.
- `eval/run_eval.py --min-pass-rate` quality gate.
- A documentation set in `docs/`, including a step-by-step DevOps guide.

### Changed
- Citations include `refs`, `document` and `sections`, so inline `[n]` markers map to sources.
- `run.py` auto-reloads only when `APP_ENV=development`.
- Ruff config in `pyproject.toml`; the codebase is lint-clean.

### Security
- 500 responses no longer expose exception text; they return an error id instead.
- 10 MB upload limit; admin key compared with `secrets.compare_digest`.

## [1.0.0] - 2026-10-18

- Multi-department (IT + HR) agentic RAG: three-way routing, a reasoning grader, cited source-only answers, contextual chunking, re-ranking.
- Role-based access control and lifecycle filtering in the vector search; a deterministic company web guard; prompt-injection screening; a PII-redacted audit log.
- A 72-question evaluation harness with an LLM judge. Pass rate went from 84.8% to 97.2%.
