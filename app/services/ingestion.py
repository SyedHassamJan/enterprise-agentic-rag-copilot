from pathlib import Path
from typing import Iterable
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from docx import Document as DocxDocument
from app.core.config import BASE_DIR


SUPPORTED = {".pdf", ".txt", ".md", ".docx"}


def source_id(path: Path) -> str:
    """Stable, machine-independent source name: project-relative when possible."""
    path = path.resolve()
    try:
        return path.relative_to(BASE_DIR).as_posix()
    except ValueError:
        # Outside the project (e.g. a custom UPLOAD_DIR): keep the department folder.
        return "/".join(path.parts[-2:])


def load_file(path: Path) -> list[Document]:
    suffix = path.suffix.lower()
    source = source_id(path)
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return [
            Document(page_content=text, metadata={"source": source, "page": i + 1})
            for i, page in enumerate(reader.pages)
            if (text := (page.extract_text() or "").strip())
        ]
    if suffix in {".txt", ".md"}:
        return [Document(page_content=path.read_text(encoding="utf-8"), metadata={"source": source})]
    if suffix == ".docx":
        doc = DocxDocument(str(path))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return [Document(page_content=text, metadata={"source": source})]
    raise ValueError(f"Unsupported file type: {suffix}")


def chunk_documents(docs: Iterable[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120, add_start_index=True)
    return splitter.split_documents(list(docs))
