# Knowledge base

## Where documents live

```text
data/sample_kb/
  it/   -> Pinecone namespace "it-kb"
  hr/   -> Pinecone namespace "hr-kb"
```

Uploads through the UI or `POST /api/ingest` are saved under `UPLOAD_DIR/<department>/` and indexed into the same namespaces.

## Document format (Markdown recommended)

```markdown
# NovaRetail HR: Corporate Salary Bands 2026 (CONFIDENTIAL)

Owner: Total Rewards Team | Effective: 2026-01-01 | Status: CURRENT | Access: hr_staff

## Corporate Salary Bands
...

## Offer Approval Rules
...
```

| Element | Effect |
|---|---|
| `# Title` | The document title. It's prefixed to every chunk and shown in citations |
| The short line before the first `##` | Document info: attached to every chunk header and parsed for `Status` and `Access` |
| `Status: SUPERSEDED` or `ARCHIVED` | Stays indexed for audit, **excluded from retrieval** |
| `Access: all / managers / hr_staff / it_staff` | Who can retrieve it (default `all`) |
| `## Section` | A chunk boundary. The section name goes into the chunk header and citations |

Each chunk is stored as `"<Title> > <Section> [<doc info>]\n<text>"`, with metadata `source`, `title`, `section`, `department`, `status` and `access`. Long sections are split at 900 characters with a 120-character overlap.

PDF, DOCX and TXT files work too. They get a title from the file name and the default status and access, unless `access` is set at upload.

## Access levels and roles

| Role | Can read |
|---|---|
| `employee` | `all` |
| `manager` | `all`, `managers` |
| `hr_staff` | `all`, `managers`, `hr_staff` |
| `it_admin` | `all`, `it_staff` |

Defined in [`app/core/access.py`](../app/core/access.py).

## Ingesting

```powershell
python ingest_sample_kb.py            # upsert every file (safe to re-run)
python ingest_sample_kb.py --reset    # wipe the department namespaces first
```

Vector IDs are `sha1(source)[:16] + "#" + chunk number`. Re-ingesting a file deletes every vector with that prefix, then writes the new chunks. A shortened document leaves no stale chunks behind, and nothing is duplicated.

## Replacing a policy with a new version

1. Add the new document with `Status: CURRENT`.
2. Change the old document's header to `Status: SUPERSEDED by <new document>`.
3. Re-ingest both. The old version stays searchable for audit purposes, but the agent never retrieves it.

## Adding a department (for example Finance)

1. Add an entry to `DEPARTMENTS` in [`app/rag/departments.py`](../app/rag/departments.py): key, label, namespace, topics, escalation contact, validation wording.
2. Put its documents in `data/sample_kb/finance/`.
3. Run `python ingest_sample_kb.py`.
4. Add finance questions to `eval/golden_set.jsonl` and run the evaluation.

The router prompt, the upload dropdown, `/api/departments` and the escalation messages all pick it up automatically.
