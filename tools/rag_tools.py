import os
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from tools.mcp_client import batch_read_resumes, list_resume_files


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESUME_FOLDER = Path(
    os.environ.get("RESUME_DIRECTORY", PROJECT_ROOT / "data" / "resumes")
).expanduser().resolve()
DB_DIR = str(PROJECT_ROOT / "vector_db")
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx"}
SKILL_TERMS = (
    "javascript", "typescript", "python", "java", "react", "node.js",
    "node", "django", "flask", "fastapi", "sql", "postgresql", "mysql",
    "mongodb", "redis", "kafka", "docker", "kubernetes", "aws", "gcp",
    "azure", "c++", "c#", "go", "rust", "ruby", "php", "pytorch",
    "tensorflow", "machine learning", "deep learning", "langchain",
    "langgraph", "spark", "hadoop", "terraform", "linux", "git",
)

_cached_db = None
_cached_db_has_embeddings = False


def _contains_term(text, term):
    pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _resume_documents():
    documents = []
    batch = batch_read_resumes(str(RESUME_FOLDER))
    if batch["errors"]:
        first_error = batch["errors"][0]
        raise RuntimeError(
            f"Unable to search resume '{first_error['path']}': {first_error['error']}"
        )
    for item in batch["files"]:
        metadata = item["metadata"]
        if Path(metadata["name"]).suffix.casefold() not in SUPPORTED_EXTENSIONS:
            continue
        text = item["content"]
        if not text.strip():
            continue
        skills = [skill for skill in SKILL_TERMS if _contains_term(text, skill)]
        experience = re.findall(r"\b(\d+)\s*\+?\s*(?:years?|yrs?)\b", text, re.I)
        name = next(
            (line.strip() for line in text.splitlines() if line.strip()),
            Path(metadata["name"]).stem.replace("_", " ").title(),
        )
        documents.append(Document(
            page_content=text,
            metadata={
                "source": metadata["path"],
                "name": name,
                "skills": skills,
                "experience_years": max((int(value) for value in experience), default=0),
            },
        ))
    return documents


def count_resumes():
    """Count supported resume files currently present in the resume folder."""
    return sum(
        Path(metadata["name"]).suffix.casefold() in SUPPORTED_EXTENSIONS
        for metadata in list_resume_files(str(RESUME_FOLDER))
    )


def _skill_search(query, documents, k):
    requested_skills = [skill for skill in SKILL_TERMS if _contains_term(query, skill)]
    if not requested_skills:
        return None
    matches = [
        (document, 0.0)
        for document in documents
        if any(_contains_term(document.page_content, skill) for skill in requested_skills)
    ]
    return matches[:max(0, k)]


def _lexical_search(query, documents, k):
    terms = set(re.findall(r"[a-z0-9+#]+", query.casefold()))
    if not terms:
        return [(document, 1.0) for document in documents[:max(0, k)]]

    ranked = []
    for document in documents:
        content_terms = set(re.findall(r"[a-z0-9+#]+", document.page_content.casefold()))
        overlap = len(terms & content_terms)
        if overlap:
            distance = 1 - overlap / max(len(terms), 1)
            ranked.append((document, distance))
    ranked.sort(key=lambda result: result[1])
    return ranked[:max(0, k)]


def load_db():

    global _cached_db

    if _cached_db is not None:
        return _cached_db

    db = Chroma(
        persist_directory=DB_DIR
    )

    _cached_db = db

    return db


def semantic_search(query, k=20):
    documents = _resume_documents()
    skill_results = _skill_search(query, documents, k)
    if skill_results is not None:
        return skill_results

    db = load_db()
    if db.get(include=[]).get("ids"):
        if not _cached_db_has_embeddings:
            db = Chroma(
                persist_directory=DB_DIR,
                embedding_function=HuggingFaceEmbeddings(
                    model_name="all-MiniLM-L6-v2"
                ),
            )
            _set_cached_db(db)
        return db.similarity_search_with_score(query, k=k)
    return _lexical_search(query, documents, k)


def _set_cached_db(db):
    """Cache the initialized vector store and its embedding model."""
    global _cached_db, _cached_db_has_embeddings
    _cached_db = db
    _cached_db_has_embeddings = True