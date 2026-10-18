"""Second-stage reranking with a cross-encoder hosted by Pinecone Inference.

Vector search compares a query embedding with chunk embeddings independently; a cross-encoder
reads the query and each candidate chunk together, which ranks "which chunk actually answers this"
far more precisely. We over-fetch candidates with vector search, then keep the best few.
"""
import logging
from langchain_core.documents import Document
from app.core.config import get_settings
from app.rag.vectorstore import get_pinecone

logger = logging.getLogger(__name__)
settings = get_settings()


def rerank(query: str, docs: list[Document], top_n: int) -> tuple[list[Document], bool]:
    """Return (best top_n docs, whether the reranker was used).

    Falls back to the original vector-search order if the reranker is disabled or unavailable,
    so a reranking outage degrades quality instead of failing the request.
    """
    if not docs:
        return [], False
    if not settings.rerank_enabled or len(docs) <= 1:
        return docs[:top_n], False
    try:
        result = get_pinecone().inference.rerank(
            model=settings.rerank_model,
            query=query,
            documents=[d.page_content for d in docs],
            top_n=min(top_n, len(docs)),
            return_documents=False,
        )
    except Exception as exc:
        logger.warning("Reranker unavailable, using vector order: %s", exc)
        return docs[:top_n], False
    ranked = []
    for item in result.data:
        doc = docs[item.index]
        doc.metadata["rerank_score"] = round(float(item.score), 4)
        ranked.append(doc)
    return ranked, True
