import hashlib
import time
from pinecone import Pinecone, ServerlessSpec
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from app.core.config import get_settings

settings = get_settings()

_embeddings = None
_index = None
_vectorstores: dict[str, PineconeVectorStore] = {}


EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "all-minilm-l6-v2": 384,
}


def get_embedding_dimension(model_name: str | None = None) -> int:
    name = (model_name or settings.embedding_model or "").strip()
    if not name:
        raise RuntimeError("Embedding model is not configured")

    normalized = name.lower()
    if normalized in EMBEDDING_DIMENSIONS:
        return EMBEDDING_DIMENSIONS[normalized]
    for known, dim in EMBEDDING_DIMENSIONS.items():
        if known in normalized:
            return dim

    raise ValueError(
        f"Unsupported embedding model '{name}' for Pinecone. "
        "Add the matching dimension to EMBEDDING_DIMENSIONS."
    )


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        _embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
        )
    return _embeddings


def ensure_index():
    global _index
    if _index is not None:
        return _index
    if not settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is missing")

    desired_dimension = get_embedding_dimension()
    pc = Pinecone(api_key=settings.pinecone_api_key)
    names = [x["name"] for x in pc.list_indexes()]

    if settings.pinecone_index_name in names:
        current_dimension = getattr(pc.describe_index(settings.pinecone_index_name), "dimension", None)
        if current_dimension is not None and current_dimension != desired_dimension:
            # Never delete an index automatically: it may hold documents that cannot be re-created.
            raise RuntimeError(
                f"Pinecone index '{settings.pinecone_index_name}' has dimension {current_dimension}, "
                f"but embedding model '{settings.embedding_model}' produces {desired_dimension}. "
                "Set a new PINECONE_INDEX_NAME or delete the old index in the Pinecone console."
            )
    else:
        pc.create_index(
            name=settings.pinecone_index_name,
            dimension=desired_dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not pc.describe_index(settings.pinecone_index_name).status["ready"]:
            time.sleep(1)

    _index = pc.Index(settings.pinecone_index_name)
    return _index


def get_vectorstore(namespace: str) -> PineconeVectorStore:
    if namespace not in _vectorstores:
        _vectorstores[namespace] = PineconeVectorStore(
            index=ensure_index(),
            embedding=get_embeddings(),
            namespace=namespace,
        )
    return _vectorstores[namespace]


def get_retriever(namespace: str):
    return get_vectorstore(namespace).as_retriever(search_kwargs={"k": settings.top_k})


def _source_prefix(source: str) -> str:
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16] + "#"


def upsert_source(chunks, namespace: str, source: str) -> list[str]:
    """Replace every vector of one source document with `chunks`.

    IDs are `<sha1(source)>#<chunk index>`, so re-ingesting the same file overwrites
    instead of duplicating, and stale chunks from a longer previous version are removed.
    """
    prefix = _source_prefix(source)
    index = ensure_index()
    for id_batch in index.list(prefix=prefix, namespace=namespace):
        if id_batch:
            index.delete(ids=list(id_batch), namespace=namespace)
    if not chunks:
        return []
    ids = [f"{prefix}{i:04d}" for i in range(len(chunks))]
    return get_vectorstore(namespace).add_documents(chunks, ids=ids)


def reset_namespace(namespace: str) -> None:
    index = ensure_index()
    stats = index.describe_index_stats()
    if namespace in (stats.get("namespaces") or {}):
        index.delete(delete_all=True, namespace=namespace)
