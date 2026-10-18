# API reference

Interactive OpenAPI docs are served at `/docs` when the app is running.

## `GET /api/health`: liveness

Returns 200 while the process is up. Used by the Docker `HEALTHCHECK` and the CI smoke test.

```json
{ "status": "ok", "service": "Enterprise Employee Support Agentic RAG Copilot", "version": "1.1.0", "env": "production" }
```

## `GET /api/ready`: readiness

Returns 200 `{"status": "ready"}` when all required keys are configured. Otherwise it returns **503**:

```json
{ "detail": { "status": "not_ready", "missing": ["PINECONE_API_KEY"] } }
```

## `GET /api/departments`

```json
[ { "key": "it", "label": "IT Support" }, { "key": "hr", "label": "HR Policy" } ]
```

## `GET /api/users`

Demo identities. In production, identity would come from SSO, not from this list.

```json
[ { "username": "alex", "name": "Alex Chen", "role": "employee" }, ... ]
```

## `POST /api/chat`

| Header | Required | Meaning |
|---|---|---|
| `Content-Type: application/json` | yes | |
| `X-Demo-User` | no | `alex` (default), `maria`, `priya`, or `sam` |

Request body:

```json
{ "question": "I'm starting remote work next week. What do I need to set up?" }
```

The question must be 2–3000 characters (otherwise 422).

Response:

```json
{
  "answer": "You need manager approval ... [1]. Connect the NovaSecure VPN ... [2].",
  "source_used": "private_kb",
  "departments": ["it", "hr"],
  "trace": ["Router → KB [IT, HR]", "Private KB retrieval → 24 candidates (IT: 12, HR: 12) → reranked 8", "..."],
  "citations": [
    { "title": "HR · company_hr_handbook.md", "department": "hr", "document": "NovaRetail Internal HR Handbook",
      "file": "company_hr_handbook.md", "sections": ["Remote Work Policy"], "refs": [1], "type": "private_kb", "url": "" }
  ],
  "rewritten_query": "I'm starting remote work next week. What do I need to set up?",
  "user": { "username": "alex", "name": "Alex Chen", "role": "employee" },
  "metrics": { "latency_ms": 4210, "total_tokens": 3120,
               "nodes": [ { "node": "route_question", "ms": 812 }, "..." ] }
}
```

`source_used` is one of:

| Value | Meaning |
|---|---|
| `private_kb` | Answered from company documents |
| `web_search` | Answered from public web evidence (flagged as external) |
| `direct` | Greeting or small talk |
| `insufficient_evidence` | Declined and escalated |

In `citations`, `refs` lists the `[n]` markers in `answer` that point to each citation. Web citations have `url` instead.

Errors: **500** returns `{"detail": "The assistant failed to answer (error id 1a2b3c4d)."}`. The full error is in the server log under the same id.

## `POST /api/ingest`

`multipart/form-data`, with header `X-Admin-Key`.

| Field | Required | Values |
|---|---|---|
| `file` | yes | `.pdf`, `.docx`, `.md`, `.txt`, up to 10 MB |
| `department` | yes | a department key (`it`, `hr`) |
| `access` | no | `all`, `managers`, `hr_staff`, `it_staff`. If empty, the document's own `Access:` header is used, defaulting to `all` |

Success response:

```json
{ "message": "Document indexed", "file": "travel.md", "department": "hr", "access": "all", "chunks": 6, "ids_created": 6 }
```

| Status | Reason |
|---|---|
| 401 | Wrong admin key |
| 400 | Unknown department or access level, or unsupported file type |
| 413 | File larger than 10 MB |
| 422 | Prompt-injection content detected; the file is deleted and not indexed |

Re-uploading the same file name to the same department **replaces** its previous vectors.
