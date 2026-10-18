"""Index data/sample_kb/<department>/ into each department's Pinecone namespace.

Safe to re-run: every file is upserted with deterministic IDs, so changed files are
replaced and unchanged files are simply overwritten (no duplicates).

    python ingest_sample_kb.py            # upsert all sample documents
    python ingest_sample_kb.py --reset    # wipe the department namespaces first
"""
import argparse
from pathlib import Path

from app.core.config import get_settings
from app.rag.departments import DEPARTMENTS
from app.rag.vectorstore import reset_namespace, upsert_source
from app.services.ingestion import SUPPORTED, chunk_documents, load_file, source_id

settings = get_settings()

parser = argparse.ArgumentParser()
parser.add_argument("--reset", action="store_true", help="delete all vectors in each department namespace first")
args = parser.parse_args()

for dept in DEPARTMENTS.values():
    folder = Path(settings.sample_kb_dir) / dept.key
    files = sorted(p for p in folder.glob("*") if p.suffix.lower() in SUPPORTED) if folder.is_dir() else []
    if args.reset:
        reset_namespace(dept.namespace)
        print(f"[{dept.key}] namespace '{dept.namespace}' cleared")
    if not files:
        print(f"[{dept.key}] no documents in {folder}, skipped")
        continue

    total = 0
    for path in files:
        chunks = chunk_documents(load_file(path))
        for c in chunks:
            c.metadata["department"] = dept.key
        total += len(upsert_source(chunks, dept.namespace, source_id(path)))
    print(f"[{dept.key}] {len(files)} files -> {total} chunks upserted into namespace '{dept.namespace}'")
