import time
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header
from langchain_core.callbacks import get_usage_metadata_callback
from pydantic import BaseModel, Field
from app.core.access import ACCESS_LEVELS, DEMO_USERS, get_user
from app.core.config import get_settings
from app.rag.departments import DEPARTMENTS
from app.rag.workflow import ask
from app.rag.vectorstore import upsert_source
from app.services.ingestion import load_file, chunk_documents, source_id, SUPPORTED
from app.services.audit import write_audit
from app.services.guardrails import detect_injection

router = APIRouter(prefix="/api")
settings = get_settings()

class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=3000)


@router.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@router.get("/departments")
def departments():
    return [{"key": d.key, "label": d.label} for d in DEPARTMENTS.values()]


@router.get("/users")
def users():
    """Demo identities. Production would derive the role from the SSO token, not a client header."""
    return [{"username": u.username, "name": u.name, "role": u.role} for u in DEMO_USERS.values()]


@router.post("/chat")
def chat(payload: ChatRequest, x_demo_user: str = Header(default="")):
    user = get_user(x_demo_user)
    try:
        with get_usage_metadata_callback() as usage:
            start = time.perf_counter()
            result = ask(payload.question, user_role=user.role)
            latency_ms = round((time.perf_counter() - start) * 1000)
        total_tokens = sum(u.get("total_tokens", 0) for u in usage.usage_metadata.values())
        write_audit(
            question=payload.question, source_used=result["source_used"],
            departments=result.get("departments", []), trace=result.get("trace", []),
            username=user.username, role=user.role, latency_ms=latency_ms, total_tokens=total_tokens,
            injection_flag=bool(detect_injection(payload.question)),
        )
        return {
            "answer": result["answer"],
            "source_used": result["source_used"],
            "departments": result.get("departments", []),
            "trace": result.get("trace", []),
            "citations": result.get("citations", []),
            "rewritten_query": result.get("current_query", payload.question),
            "user": {"username": user.username, "name": user.name, "role": user.role},
            "metrics": {"latency_ms": latency_ms, "total_tokens": total_tokens, "nodes": result.get("timings", [])},
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    department: str = Form(...),
    access: str = Form(default=""),  # empty = use the document's own "Access:" header, else "all"
    x_admin_key: str = Header(default=""),
):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    if department not in DEPARTMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown department. Valid: {', '.join(DEPARTMENTS)}")
    if access and access not in ACCESS_LEVELS:
        raise HTTPException(status_code=400, detail=f"Unknown access level. Valid: {', '.join(ACCESS_LEVELS)}")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Supported: {', '.join(sorted(SUPPORTED))}")
    upload_dir = Path(settings.upload_dir) / department
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / Path(file.filename).name
    dest.write_bytes(await file.read())
    docs = load_file(dest)

    # Indirect prompt injection: instructions hidden inside a document would later reach the LLM
    # as "evidence". Reject such files for human review instead of indexing them.
    suspicious = sorted({hit for d in docs for hit in detect_injection(d.page_content)})
    if suspicious:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Document rejected: possible prompt injection ({'; '.join(suspicious[:3])})")

    chunks = chunk_documents(docs, access_override=access or None)
    for c in chunks:
        c.metadata["department"] = department
    ids = upsert_source(chunks, DEPARTMENTS[department].namespace, source_id(dest))
    effective = chunks[0].metadata["access"] if chunks else (access or "all")
    return {"message": "Document indexed", "file": dest.name, "department": department, "access": effective,
            "chunks": len(chunks), "ids_created": len(ids)}
