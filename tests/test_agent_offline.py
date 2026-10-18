"""Offline tests: the real LangGraph graph and FastAPI app, with the LLM, Pinecone and
Tavily replaced by fakes. No API keys or network needed, so these run in CI."""
import os
import sqlite3
import tempfile

os.environ.setdefault("AUDIT_DB_PATH", os.path.join(tempfile.mkdtemp(), "audit.db"))
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp())
os.environ["ADMIN_API_KEY"] = "test-admin-key"

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from app.core.config import get_settings
from app.rag import workflow
import app.api.routes as routes
from app.rag.vectorstore import _source_prefix
from app.services.ingestion import source_id

SCENARIO: dict = {}


class Msg:
    def __init__(self, content):
        self.content = content


class FakeStructured:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, prompt):
        if self.schema.__name__ == "RouteDecision":
            return self.schema(**SCENARIO["route"])
        key = "web_grades" if "Web evidence" in prompt else "kb_grades"
        return self.schema(grade=SCENARIO[key].pop(0))


class FakeLLM:
    def with_structured_output(self, schema, method=None):
        return FakeStructured(schema)

    def invoke(self, prompt):
        SCENARIO.setdefault("prompts", []).append(prompt)
        return Msg("rewritten query" if prompt.lstrip().startswith("Rewrite") else "ANSWER")


class FakeRetriever:
    def __init__(self, namespace):
        self.namespace = namespace

    def invoke(self, query):
        SCENARIO.setdefault("searched", []).append(self.namespace)
        return [Document(page_content=f"{self.namespace} text", metadata={"source": f"data/sample_kb/{self.namespace}/doc.md"})]


class FakeWeb:
    def invoke(self, query):
        return {"answer": "web", "results": [{"title": "T", "url": "https://example.com", "content": "c"}]}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(workflow, "llm", lambda: FakeLLM())
    monkeypatch.setattr(workflow, "get_retriever", lambda ns: FakeRetriever(ns))
    monkeypatch.setattr(workflow, "web_search_tool", lambda: FakeWeb())
    SCENARIO.clear()


def run(route, kb=(), web=()):
    SCENARIO.update(route=route, kb_grades=list(kb), web_grades=list(web))
    return workflow.ask("question?")


def test_single_department_answers_from_kb():
    r = run({"route": "kb", "departments": ["it"]}, kb=["good"])
    assert r["source_used"] == "private_kb"
    assert r["departments"] == ["it"]
    assert SCENARIO["searched"] == ["it-kb"]
    assert r["citations"][0]["title"] == "IT · doc.md"


def test_cross_department_searches_each_namespace_once():
    r = run({"route": "kb", "departments": ["hr", "it", "hr"]}, kb=["good"])
    assert SCENARIO["searched"] == ["hr-kb", "it-kb"]
    assert {c["department"] for c in r["citations"]} == {"hr", "it"}


def test_unknown_department_falls_back_to_all():
    r = run({"route": "kb", "departments": ["finance"]}, kb=["good"])
    assert r["departments"] == ["it", "hr"]


def test_direct_route_skips_retrieval():
    r = run({"route": "direct", "departments": []})
    assert r["source_used"] == "direct"
    assert "searched" not in SCENARIO


def test_weak_kb_falls_back_to_web_with_department_validation_warning():
    r = run({"route": "kb", "departments": ["hr"]}, kb=["weak"], web=["good"])
    assert r["source_used"] == "web_search"
    assert "HR validation" in SCENARIO["prompts"][-1]


def test_retry_then_insufficient_escalates_to_department():
    r = run({"route": "kb", "departments": ["it"]}, kb=["weak", "weak"], web=["weak", "weak"])
    assert r["source_used"] == "insufficient_evidence"
    assert "IT Service Desk" in r["answer"]
    assert r["retry_count"] == 1
    assert r["current_query"] == "rewritten query"
    assert SCENARIO["searched"] == ["it-kb", "it-kb"]


def test_vector_ids_are_deterministic_per_source():
    assert _source_prefix("data/sample_kb/hr/a.md") == _source_prefix("data/sample_kb/hr/a.md")
    assert _source_prefix("data/sample_kb/hr/a.md") != _source_prefix("data/sample_kb/hr/b.md")


def test_source_id_is_project_relative():
    from app.core.config import BASE_DIR
    assert source_id(BASE_DIR / "data" / "sample_kb" / "it" / "x.md") == "data/sample_kb/it/x.md"


@pytest.fixture
def client(monkeypatch):
    upserts = {}

    def fake_upsert(chunks, namespace, source):
        upserts[namespace] = (source, chunks)
        return [f"id{i}" for i in range(len(chunks))]

    monkeypatch.setattr(routes, "upsert_source", fake_upsert)
    from app.main import app
    c = TestClient(app)
    c.upserts = upserts
    return c


def test_departments_endpoint(client):
    assert client.get("/api/departments").json() == [
        {"key": "it", "label": "IT Support"},
        {"key": "hr", "label": "HR Policy"},
    ]


def test_chat_endpoint_returns_departments_and_writes_audit(client):
    SCENARIO.update(route={"route": "kb", "departments": ["hr"]}, kb_grades=["good"], web_grades=[])
    body = client.post("/api/chat", json={"question": "leave days?"}).json()
    assert body["departments"] == ["hr"] and body["source_used"] == "private_kb"
    row = sqlite3.connect(get_settings().audit_db_path).execute(
        "select source_used, departments from query_audit order by id desc limit 1").fetchone()
    assert row == ("private_kb", "hr")


def test_ingest_validates_key_and_department(client):
    f = ("policy.md", b"# Expenses\nLaptops over $500 need approval.", "text/markdown")
    headers = {"X-Admin-Key": "test-admin-key"}
    assert client.post("/api/ingest", files={"file": f}, data={"department": "hr"}, headers={"X-Admin-Key": "bad"}).status_code == 401
    assert client.post("/api/ingest", files={"file": f}, data={"department": "finance"}, headers=headers).status_code == 400
    ok = client.post("/api/ingest", files={"file": f}, data={"department": "hr"}, headers=headers)
    assert ok.status_code == 200 and ok.json()["department"] == "hr"
    source, chunks = client.upserts["hr-kb"]
    assert source.endswith("hr/policy.md")
    assert chunks[0].metadata["department"] == "hr"
