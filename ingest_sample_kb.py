from pathlib import Path
from app.core.config import get_settings
from app.rag.departments import DEPARTMENTS
from app.services.ingestion import load_file, chunk_documents
from app.rag.vectorstore import add_documents

settings = get_settings()

# Each department's documents live in data/sample_kb/<key>/ and go to that department's namespace.
for dept in DEPARTMENTS.values():
    folder = Path(settings.sample_kb_dir) / dept.key
    files = [p for p in folder.iterdir() if p.is_file()] if folder.is_dir() else []
    if not files:
        print(f"[{dept.key}] no documents in {folder}, skipped")
        continue

    all_docs = []
    for path in files:
        all_docs.extend(load_file(path))
    chunks = chunk_documents(all_docs)
    for c in chunks:
        c.metadata["department"] = dept.key
    ids = add_documents(chunks, dept.namespace)
    print(f"[{dept.key}] Indexed {len(files)} files -> {len(chunks)} chunks -> {len(ids)} vectors in namespace '{dept.namespace}'")
