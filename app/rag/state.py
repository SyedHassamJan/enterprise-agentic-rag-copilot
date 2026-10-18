from typing import List, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.documents import Document

class RouteDecision(BaseModel):
    route: Literal["kb", "web", "direct"] = Field(
        description="kb for company-specific questions; web for general public knowledge; direct for greetings/small talk"
    )
    departments: List[str] = Field(default_factory=list, description="Department keys whose knowledge base should be searched (route=kb only)")

class EvidenceGrade(BaseModel):
    # Reasoning comes first so the model commits to an analysis before the verdict.
    reasoning: str = Field(description="One or two sentences: what the question asks and which chunks address it")
    relevant_ids: List[int] = Field(default_factory=list, description="Numbers of the chunks that help answer the question")
    grade: Literal["good", "weak"] = Field(description="good if the relevant chunks answer the core of the question")

class WebGrade(BaseModel):
    grade: Literal["good", "weak"] = Field(description="Whether the web evidence is sufficient and directly relevant")

class AgentState(TypedDict):
    question: str
    current_query: str
    route: str
    departments: List[str]
    kb_docs: List[Document]
    web_results: str
    kb_grade: str
    web_grade: str
    answer: str
    source_used: str
    retry_count: int
    trace: List[str]
    citations: List[dict]
