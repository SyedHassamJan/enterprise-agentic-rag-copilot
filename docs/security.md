# Security

## Controls

| Threat | Control | Where |
|---|---|---|
| An employee reads confidential documents | Role-based access filter **inside** the Pinecone query, so restricted chunks are never retrieved | `app/core/access.py`, `retrieve_kb` |
| An outdated policy is quoted | `status ≠ superseded` in the same filter | `retrieval_filter()` |
| Prompt injection in a question | Pattern flag in the trace and audit; prompts treat retrieved text as data; answers restricted to cited sources | `guardrails.detect_injection`, `workflow.py` |
| Prompt injection inside a document (indirect) | Uploads containing injection patterns are rejected with **422** before indexing | `POST /api/ingest` |
| Another organization's data presented as company policy | A deterministic check that web evidence mentions NovaRetail for company questions, plus an LLM grade | `grade_web` |
| Hallucinated advice or contacts | Source-only, cited generation; escalation limited to the registry contact; faithfulness measured by the evaluation | `generate_from_kb`, `eval/` |
| Personal data in logs | Emails, phone numbers, SSNs and card numbers redacted before the audit write | `guardrails.redact_pii`, `audit.py` |
| Internal errors leaking to clients | Generic 500 with an error id; details only in the server log | `routes.chat` |
| Upload abuse | Admin key compared with `secrets.compare_digest`; 10 MB limit; extension allow-list; file name stripped of paths | `routes.ingest` |
| Container compromise | Non-root user, slim base image, no secrets baked into the image (`.env` is excluded) | `Dockerfile`, `.dockerignore` |
| Secrets in git | `.env` is git-ignored; CI uses GitHub encrypted secrets | `.gitignore`, workflows |

Access control is covered by six evaluation pairs: the same question asked by an authorized and an unauthorized role. All six pass, with zero leaks.

## Known gaps (be upfront about these)

- **Identity is a demo.** `X-Demo-User` is client-controlled. Production needs SSO/OIDC, with the role taken from verified token claims on the server.
- **Injection detection uses patterns.** It catches common phrasings, not paraphrases. The structural controls (filtering and source-only answers) are the main defence.
- **No rate limiting.** Add it at the gateway or reverse proxy (or with `slowapi`) before exposing the app publicly.
- **A single shared admin key.** Replace it with per-user upload permissions tied to SSO groups.
- **Upload scanning is text-based.** There's no malware scan of binary files.
- **SQLite audit log.** Fine for one instance. Use Postgres or a log pipeline when running several replicas.

## Reporting

This is a portfolio project. Please open a GitHub issue for any security concern.
