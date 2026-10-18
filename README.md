# Enterprise Employee Support Agentic RAG Copilot

One internal copilot for **IT support and HR policy** questions. A LangGraph agent routes each question to the right department's private knowledge base, grades the evidence before answering, falls back to web search when internal knowledge is insufficient, rewrites and retries weak queries, and refuses rather than guesses. Every decision is shown in a live trace and written to an audit log.

**Stack:** LangGraph · LangChain · OpenAI · Pinecone · Tavily · FastAPI · HTML/CSS/JS · SQLite · Docker

---

## The problem

NovaRetail (a fictional 3,000-employee company) keeps IT runbooks and HR policies in separate places. Employees don't know which team owns which answer, so they file repetitive tickets with both. Keyword search returns too many documents, and a generic chatbot may invent policy.

Real questions don't respect org charts either. *"I'm starting remote work next week. What do I need to set up and what are the rules?"* needs IT (VPN, MFA) **and** HR (remote-work policy).

## What the agent does

```text
Question
   │
[1] Route ──── greeting ─────────────────────────────► Direct answer
   │
   │ picks one or more departments: IT, HR, or both
   ▼
[2] Retrieve from each selected department's Pinecone namespace
   ▼
[3] Grade private evidence ── GOOD ──► Answer from KB, with department-tagged citations
   │ WEAK
   ▼
[4] Tavily web search ─► [5] Grade web evidence ── GOOD ──► Answer from web + "needs IT/HR validation"
                                   │ WEAK
                                   ▼
                     [6] Rewrite query → retry from [2]  (max 1 retry)
                                   ▼
                     Insufficient evidence → "contact the IT Service Desk / HR team"
```

### Multi-department routing

Departments are defined once in [`app/rag/departments.py`](app/rag/departments.py):

```python
"hr": Department(key="hr", label="HR Policy", namespace="hr-kb",
                 topics="leave, payroll, benefits, remote work, ...",
                 escalation="the HR team",
                 validation="HR validation before being treated as company policy ..."),
```

Everything reads from that registry: the router prompt, the retrieval namespaces, the escalation and validation wording, the ingestion script, the `/api/departments` endpoint and the upload dropdown in the UI.

- **Cross-department questions** search several namespaces, and the merged evidence is graded together.
- **If the router picks an unknown department, it searches every KB** rather than none.
- **Adding a department** (Finance, Legal, …) is one registry entry plus a folder `data/sample_kb/<key>/`. No graph changes are needed.

---

## Run it

**Prerequisites:** Python 3.11+, plus API keys for **OpenAI**, **Pinecone** (free tier) and **Tavily** (free tier).

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

copy .env.example .env               # then fill in the 4 keys
python ingest_sample_kb.py           # once: indexes data/sample_kb/it -> it-kb, data/sample_kb/hr -> hr-kb
python run.py                        # http://127.0.0.1:8080   (API docs: /docs)
```

> Run `ingest_sample_kb.py` only once. Running it again adds duplicate vectors.

### Try these

| Question | Expected route |
|---|---|
| `Hello!` | DIRECT |
| `How do I connect to the company VPN?` | KB [IT] → GOOD → private KB |
| `How many annual leave days do employees receive?` | KB [HR] → GOOD → private KB |
| `I'm starting remote work next week. What do I need to set up and what are the rules?` | KB [IT, HR] → GOOD → citations from both |
| `What is the latest Microsoft Teams outage guidance?` | KB [IT] → WEAK → Tavily → web answer |

### Docker

```powershell
docker build -t employee-copilot .
docker run --env-file .env -p 8080:8080 employee-copilot
```

---

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | Liveness |
| GET | `/api/departments` | `[{"key":"it","label":"IT Support"}, ...]` |
| POST | `/api/chat` | `{"question": "..."}` returns `answer`, `source_used`, `departments`, `trace`, `citations`, `rewritten_query` |
| POST | `/api/ingest` | multipart `file` + form field `department`, plus header `X-Admin-Key`. Indexes the file into that department's namespace |

The audit log is stored in `data/audit.db`, table `query_audit` (question, source, departments, trace, timestamp).

## Project layout

```text
app/
  api/routes.py          chat, ingest, departments, health
  core/config.py         settings from .env
  rag/departments.py     department registry (single source of truth)
  rag/state.py           LangGraph state + structured router/grader schemas
  rag/vectorstore.py     OpenAI embeddings + Pinecone (one index, namespace per department)
  rag/workflow.py        the agent graph
  services/ingestion.py  PDF/TXT/MD/DOCX loading + chunking
  services/audit.py      SQLite audit log
data/sample_kb/it/       IT handbook + service desk runbook
data/sample_kb/hr/       HR handbook + HR operations runbook
templates/, static/      web UI
Agentic-RAG-demo/        original notebook prototype
```

## Known limitations / roadmap

- The answer and trace are returned at the end of the request. They are not streamed yet.
- There is no evaluation set yet. Next step: score routing accuracy, grading accuracy and faithfulness.
- Re-ingesting the same file creates duplicate vectors. There are no deterministic IDs yet.
- There is a single shared admin key and no user authentication on chat.
- Planned: free model option (Groq + local HuggingFace embeddings), tool calling (create ticket, check status), conversation memory, hybrid search with re-ranking.

## Credits

This project builds on two single-department reference projects by **Bappy Ahmed ([@entbappy](https://github.com/entbappy))**, licensed under Apache 2.0:

- [Enterprise-IT-Support-Agentic-RAG-Copilot](https://github.com/entbappy/Enterprise-IT-Support-Agentic-RAG-Copilot)
- [Enterprise-HR-Policy-Employee-Support-Agentic-RAG-Copilot](https://github.com/entbappy/Enterprise-HR-Policy-Employee-Support-Agentic-RAG-Copilot)

**What this repo changes:**

- Merges the IT and HR copilots into a single multi-department agent.
- Adds a department registry and multi-label routing: one, several, or all departments, with a safe fallback.
- Gives each department its own Pinecone namespace, retrieves across departments, and adds department-aware prompts, escalation and citations.
- Adds department-scoped document upload (API and UI) and records departments in the audit log.
- Replaces automatic index deletion on an embedding-dimension mismatch with an explicit error.
- Fixes Windows citation paths, unifies the sample data, and rewrites the documentation.
