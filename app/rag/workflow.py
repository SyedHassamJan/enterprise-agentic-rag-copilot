import logging
from pathlib import Path
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END
from app.core.config import get_settings
from app.rag.departments import DEPARTMENTS
from app.rag.state import AgentState, RouteDecision, EvidenceGrade
from app.rag.vectorstore import get_retriever

logger = logging.getLogger(__name__)
settings = get_settings()

_llm = None
_web_search = None

def llm():
    global _llm
    if _llm is None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        _llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            api_key=settings.openai_api_key,
        )
    return _llm

def web_search_tool():
    global _web_search
    if _web_search is None:
        if not settings.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is missing")
        _web_search = TavilySearch(
            tavily_api_key=settings.tavily_api_key,
            max_results=5,
            topic="general",
            include_answer=True,
            include_raw_content=False,
        )
    return _web_search

def add_trace(state: AgentState, message: str):
    return [*state.get("trace", []), message]

def selected(state: AgentState):
    return [DEPARTMENTS[k] for k in state.get("departments", [])]

def labels(state: AgentState) -> str:
    return " + ".join(d.label for d in selected(state)) or "company"

def route_question(state: AgentState):
    catalog = "\n".join(f'- "{d.key}" ({d.label}): {d.topics}' for d in DEPARTMENTS.values())
    router = llm().with_structured_output(RouteDecision, method="json_mode")
    decision = router.invoke(f"""
You route messages for an enterprise employee support assistant that serves several departments.
Use route "kb" for any question about company policies, procedures, systems, or employee support,
and list every department whose knowledge base could contain the answer (usually one; several only
when the question genuinely spans them, e.g. expensing a work laptop touches both IT and HR).
Use route "direct" only for greetings, thanks, or casual chat that needs no company knowledge.

Departments:
{catalog}

Question: {state['question']}
Return valid JSON like {{"route":"kb","departments":["it"]}} or {{"route":"direct","departments":[]}}.
""")
    if decision.route == "direct":
        return {"source_used": "direct", "departments": [], "trace": add_trace(state, "Router → DIRECT")}

    departments = [k for k in dict.fromkeys(decision.departments) if k in DEPARTMENTS]
    if not departments:
        # Router could not pick a known department: search every KB rather than none.
        departments = list(DEPARTMENTS)
    names = ", ".join(k.upper() for k in departments)
    return {"source_used": "kb", "departments": departments, "trace": add_trace(state, f"Router → KB [{names}]")}

def route_after_router(state: AgentState) -> Literal["retrieve_kb", "direct_answer"]:
    return "retrieve_kb" if state["source_used"] == "kb" else "direct_answer"

def retrieve_kb(state: AgentState):
    docs, counts = [], []
    for dept in selected(state):
        found = get_retriever(dept.namespace).invoke(state["current_query"])
        for d in found:
            d.metadata["department"] = dept.key
        docs.extend(found)
        counts.append(f"{dept.key.upper()}: {len(found)}")
    return {"kb_docs": docs, "trace": add_trace(state, f"Private KB retrieval → {len(docs)} chunks ({', '.join(counts)})")}

def format_kb(state: AgentState) -> str:
    return "\n\n".join(
        f"[Source: {Path(d.metadata.get('source', 'unknown')).name} | Dept: {d.metadata.get('department', '?').upper()}]\n{d.page_content}"
        for d in state["kb_docs"]
    )

def grade_kb(state: AgentState):
    grader = llm().with_structured_output(EvidenceGrade, method="json_mode")
    grade = grader.invoke(f"""
You grade evidence for an enterprise employee support assistant ({labels(state)}).
Question: {state['question']}
Private company KB evidence:\n{format_kb(state)}
Return good only if the evidence is sufficient to answer confidently and specifically.
Otherwise return weak. JSON: {{"grade":"good"}} or {{"grade":"weak"}}.
""")
    return {"kb_grade": grade.grade, "trace": add_trace(state, f"KB evidence grade → {grade.grade.upper()}")}

def after_kb(state: AgentState) -> Literal["generate_from_kb", "search_web"]:
    return "generate_from_kb" if state["kb_grade"] == "good" else "search_web"

def search_web(state: AgentState):
    result = web_search_tool().invoke({"query": state["current_query"]})
    lines, citations = [], []
    if isinstance(result, dict):
        if result.get("answer"):
            lines.append("Search answer: " + result["answer"])
        for item in result.get("results", []):
            title, url, content = item.get("title", ""), item.get("url", ""), item.get("content", "")
            lines.append(f"Title: {title}\nURL: {url}\nContent: {content}")
            citations.append({"title": title or url, "url": url, "type": "web"})
    else:
        lines.append(str(result))
    return {
        "web_results": "\n\n".join(lines),
        "citations": citations,
        "source_used": "web",
        "trace": add_trace(state, "Web fallback → Tavily search"),
    }

def grade_web(state: AgentState):
    grader = llm().with_structured_output(EvidenceGrade, method="json_mode")
    grade = grader.invoke(f"""
Question: {state['question']}
Web evidence:\n{state['web_results']}
Return good if the evidence is sufficient and directly relevant; otherwise weak.
Return valid JSON like {{"grade":"good"}}.
""")
    return {"web_grade": grade.grade, "trace": add_trace(state, f"Web evidence grade → {grade.grade.upper()}")}

def after_web(state: AgentState) -> Literal["generate_from_web", "rewrite_query", "insufficient"]:
    if state["web_grade"] == "good":
        return "generate_from_web"
    if state["retry_count"] < settings.max_retries:
        return "rewrite_query"
    return "insufficient"

def rewrite_query(state: AgentState):
    rewritten = llm().invoke(f"""
Rewrite this {labels(state)} question for better private knowledge retrieval and public web search.
Preserve intent, add useful domain keywords, do not answer, return only the query.
Question: {state['question']}
""").content.strip()
    return {
        "current_query": rewritten,
        "retry_count": state["retry_count"] + 1,
        "trace": add_trace(state, f"Query rewrite → {rewritten}"),
    }

def generate_from_kb(state: AgentState):
    answer = llm().invoke(f"""
You are an enterprise employee support copilot covering {labels(state)}. Answer ONLY from the private company KB below.
Be concise, actionable, respectful, and safe. If steps are present, present them clearly.
Do not invent policy details. Mention that the answer is based on the company's private knowledge base.
Question: {state['question']}\n\nPrivate KB:\n{format_kb(state)}
""").content
    citations, seen = [], set()
    for d in state["kb_docs"]:
        src = Path(d.metadata.get("source", "Private KB")).name
        dept = d.metadata.get("department", "")
        if (src, dept) not in seen:
            seen.add((src, dept))
            citations.append({"title": f"{dept.upper()} · {src}" if dept else src, "url": "", "type": "private_kb", "department": dept})
    return {"answer": answer, "source_used": "private_kb", "citations": citations, "trace": add_trace(state, "Answer generation → PRIVATE KB")}

def generate_from_web(state: AgentState):
    validation = "; ".join(d.validation for d in selected(state)) or "validation by the relevant company team"
    answer = llm().invoke(f"""
You are an enterprise employee support copilot covering {labels(state)}. The private company KB was insufficient.
Answer ONLY from the web evidence below. Clearly say this is external public information and may require {validation}.
Question: {state['question']}\n\nWeb evidence:\n{state['web_results']}
""").content
    return {"answer": answer, "source_used": "web_search", "trace": add_trace(state, "Answer generation → WEB SEARCH")}

def direct_answer(state: AgentState):
    answer = llm().invoke(f"Respond briefly and naturally to: {state['question']}").content
    return {"answer": answer, "source_used": "direct", "trace": add_trace(state, "Direct response → no retrieval")}

def insufficient(state: AgentState):
    contacts = " or ".join(d.escalation for d in selected(state)) or "the relevant support team"
    return {
        "answer": f"I couldn't find enough reliable evidence in the company knowledge base or external search to answer confidently. Please contact {contacts} or provide more details.",
        "source_used": "insufficient_evidence",
        "trace": add_trace(state, "Stopped → insufficient reliable evidence"),
    }

def build_graph():
    graph = StateGraph(AgentState)
    for name, fn in {
        "route_question": route_question,
        "retrieve_kb": retrieve_kb,
        "grade_kb": grade_kb,
        "search_web": search_web,
        "grade_web": grade_web,
        "rewrite_query": rewrite_query,
        "generate_from_kb": generate_from_kb,
        "generate_from_web": generate_from_web,
        "direct_answer": direct_answer,
        "insufficient": insufficient,
    }.items():
        graph.add_node(name, fn)

    graph.add_edge(START, "route_question")
    graph.add_conditional_edges("route_question", route_after_router, {
        "retrieve_kb": "retrieve_kb", "direct_answer": "direct_answer"
    })
    graph.add_edge("retrieve_kb", "grade_kb")
    graph.add_conditional_edges("grade_kb", after_kb, {
        "generate_from_kb": "generate_from_kb", "search_web": "search_web"
    })
    graph.add_edge("search_web", "grade_web")
    graph.add_conditional_edges("grade_web", after_web, {
        "generate_from_web": "generate_from_web", "rewrite_query": "rewrite_query", "insufficient": "insufficient"
    })
    graph.add_edge("rewrite_query", "retrieve_kb")
    graph.add_edge("generate_from_kb", END)
    graph.add_edge("generate_from_web", END)
    graph.add_edge("direct_answer", END)
    graph.add_edge("insufficient", END)
    return graph.compile()

agent_graph = build_graph()

def ask(question: str):
    initial: AgentState = {
        "question": question,
        "current_query": question,
        "departments": [],
        "kb_docs": [],
        "web_results": "",
        "kb_grade": "",
        "web_grade": "",
        "answer": "",
        "source_used": "",
        "retry_count": 0,
        "trace": [],
        "citations": [],
    }
    return agent_graph.invoke(initial)
