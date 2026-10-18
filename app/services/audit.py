import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.services.guardrails import redact_pii

settings = get_settings()

COLUMNS = {
    "created_at": "TEXT NOT NULL",
    "username": "TEXT NOT NULL DEFAULT ''",
    "role": "TEXT NOT NULL DEFAULT ''",
    "question": "TEXT NOT NULL",
    "source_used": "TEXT NOT NULL",
    "departments": "TEXT NOT NULL DEFAULT ''",
    "latency_ms": "INTEGER",
    "total_tokens": "INTEGER",
    "injection_flag": "INTEGER NOT NULL DEFAULT 0",
    "trace_json": "TEXT NOT NULL",
}


def init_db() -> None:
    Path(settings.audit_db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.audit_db_path)
    cols = ", ".join(f"{name} {kind}" for name, kind in COLUMNS.items())
    con.execute(f"CREATE TABLE IF NOT EXISTS query_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})")
    # Lightweight migration: add columns introduced after an older audit.db was created.
    existing = {row[1] for row in con.execute("PRAGMA table_info(query_audit)")}
    for name, kind in COLUMNS.items():
        if name not in existing:
            con.execute(f"ALTER TABLE query_audit ADD COLUMN {name} {kind}")
    con.commit()
    con.close()


def write_audit(*, question: str, source_used: str, departments: list[str], trace: list[str],
                username: str = "", role: str = "", latency_ms: int | None = None,
                total_tokens: int | None = None, injection_flag: bool = False) -> None:
    """Store one request. Free text is PII-redacted before it touches disk."""
    con = sqlite3.connect(settings.audit_db_path)
    con.execute(
        "INSERT INTO query_audit(created_at, username, role, question, source_used, departments, "
        "latency_ms, total_tokens, injection_flag, trace_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now(UTC).isoformat(), username, role, redact_pii(question), source_used,
         ",".join(departments), latency_ms, total_tokens, int(injection_flag),
         json.dumps([redact_pii(t) for t in trace])),
    )
    con.commit()
    con.close()
