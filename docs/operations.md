# Operations

## Run locally (Python)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env        # fill in the keys
python ingest_sample_kb.py
python run.py                 # http://127.0.0.1:8080
```

## Run locally (Docker)

See the [DevOps guide](devops-guide.md). The short version:

```powershell
docker compose up --build
docker compose run --rm app python ingest_sample_kb.py
```

## Health

| Endpoint | Use |
|---|---|
| `/api/health` | Liveness: restart the container if this fails |
| `/api/ready` | Readiness: don't send traffic until this returns 200 |

## Logs

Logs go to stdout in the form `time | level | logger | message`. In Docker, use `docker compose logs -f app`. A failed chat request logs a stack trace with an `error_id`; the user sees only that id.

## Audit log

SQLite, at `AUDIT_DB_PATH` (table `query_audit`).

```powershell
python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/audit.db').execute('select created_at, username, role, source_used, departments, latency_ms, total_tokens, injection_flag, question from query_audit order by id desc limit 20')]"
```

Useful queries:

```sql
-- How often each route is used
SELECT source_used, COUNT(*) FROM query_audit GROUP BY source_used;
-- Slowest requests
SELECT question, latency_ms FROM query_audit ORDER BY latency_ms DESC LIMIT 10;
-- Prompt-injection attempts
SELECT created_at, username, question FROM query_audit WHERE injection_flag = 1;
-- Questions nobody could answer: candidates for new documents
SELECT question FROM query_audit WHERE source_used = 'insufficient_evidence';
```

The schema migrates itself: new columns are added on startup if an older `audit.db` exists.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/api/ready` returns 503 | Missing keys | Check `.env` (local) or the container environment and secrets |
| Every answer says "insufficient evidence" | The knowledge base isn't ingested, or the wrong index or namespace | Run `python ingest_sample_kb.py` and check `PINECONE_INDEX_NAME` |
| "Pinecone index ... has dimension X" | The embedding model changed | Use a new `PINECONE_INDEX_NAME` and re-ingest (see [configuration](configuration.md)) |
| Log warning "Reranker unavailable" | Pinecone re-rank quota or outage | The app falls back to vector order automatically; set `RERANK_ENABLED=false` to silence it |
| `insufficient_quota` / 429 from OpenAI | No API credit | Add billing credit |
| The server stops responding after a code edit (Windows) | Auto-reload watcher stalled | Stop and restart, or set `APP_ENV=production` to disable reload |
| `No space left on device` during `pip install` | Drive C: is full | Free space, or set `TEMP`, `TMP` and `PIP_CACHE_DIR` to another drive |
