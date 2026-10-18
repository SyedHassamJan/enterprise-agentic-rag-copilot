# Configuration

Settings are read from environment variables, or from a `.env` file in the project root (see `.env.example`). Names aren't case-sensitive. Defaults live in [`app/core/config.py`](../app/core/config.py).

## Required

| Variable | Used for |
|---|---|
| `OPENAI_API_KEY` | Chat model (routing, grading, writing) and embeddings |
| `PINECONE_API_KEY` | Vector index and the hosted re-ranker |
| `TAVILY_API_KEY` | Web search |
| `ADMIN_API_KEY` | Protects `POST /api/ingest`. Use a long random string |

`GET /api/ready` returns 503 and lists the names of any missing required keys, never their values.

## Optional

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `development` turns on auto-reload in `run.py`. The Docker image sets `production` |
| `APP_VERSION` | `1.1.0` | Shown by `/api/health` and used to bust the static-file cache |
| `HOST` / `PORT` | `127.0.0.1` / `8080` | The Docker image uses `0.0.0.0`. Hosting platforms usually set `PORT` |
| `PINECONE_INDEX_NAME` | `fde-employee-support-rag` | Created on first use: serverless, AWS us-east-1, cosine |
| `OPENAI_MODEL` | `gpt-4o-mini` | Any chat model that supports `temperature=0` and JSON mode |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Changing it changes the vector dimension, so use a **new index name** |
| `TOP_K` | `4` | Chunks kept per selected department after re-ranking |
| `FETCH_K` | `12` | Vector-search candidates per department before re-ranking |
| `RERANK_ENABLED` | `true` | Set to `false` to use vector order (for example if the re-rank quota runs out) |
| `RERANK_MODEL` | `bge-reranker-v2-m3` | Pinecone Inference model |
| `MAX_RETRIES` | `1` | Query-rewrite retries before escalating |
| `AUDIT_DB_PATH` | `data/audit.db` | `/app/var/audit.db` in Docker (on the volume) |
| `UPLOAD_DIR` | `uploads/` | `/app/var/uploads` in Docker (on the volume) |

## Changing the embedding model safely

The app **refuses to start retrieval** if the index dimension doesn't match the embedding model; it doesn't delete the index. To switch models:

1. Set a new `PINECONE_INDEX_NAME`.
2. Run `python ingest_sample_kb.py` (and re-upload any custom documents).
3. Delete the old index in the Pinecone console once you're satisfied.
