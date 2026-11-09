import os
import re
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader
)

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

from langchain_chroma import Chroma

from langchain_huggingface import (
    HuggingFaceEmbeddings
)

PROJECT_ROOT = Path(__file__).resolve().parent
RESUME_FOLDER = str(PROJECT_ROOT / "data" / "resumes")

DB_DIR = str(PROJECT_ROOT / "vector_db")


def load_documents(folder_path):

    documents = []

    for file in os.listdir(folder_path):

        file_path = os.path.join(
            folder_path,
            file
        )

        try:

            if file.endswith(".pdf"):

                loader = PyPDFLoader(
                    file_path
                )

            elif file.endswith(".txt"):

                loader = TextLoader(
                    file_path,
                    encoding="utf-8"
                )

            elif file.endswith(".docx"):

                loader = Docx2txtLoader(
                    file_path
                )

            else:
                continue

            docs = loader.load()

            for d in docs:

                d.metadata["source"] = (
                    file_path
                )

            documents.extend(docs)

        except Exception as e:

            print(
                f"Error loading {file}: {e}"
            )

    return documents


def chunk_documents(documents):

    splitter = (
        RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100
        )
    )

    return splitter.split_documents(
        documents
    )


def extract_metadata(text):

    metadata = {}

    lines = text.split("\n")

    name = "Unknown"

    for line in lines[:15]:

        clean = line.strip()

        if len(clean) > 3 and len(clean) < 40:

            name = clean

            break

    metadata["name"] = name

    skills_list = [
        "Python",
        "Java",
        "React",
        "Node",
        "AI",
        "ML",
        "SQL",
        "Django",
        "Flask"
    ]

    detected_skills = []

    for skill in skills_list:

        if re.search(
            rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])",
            text,
            re.IGNORECASE,
        ):
            detected_skills.append(skill)

    metadata["skills"] = (
        ", ".join(detected_skills)
    )

    exp_match = re.search(
        r'(\d+)\+?\s*(years|yrs)',
        text.lower()
    )

    metadata["experience_years"] = (
        int(exp_match.group(1))
        if exp_match else 0
    )

    return metadata


def create_vector_db(chunks):

    embedding = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2"
    )

    processed_chunks = []

    resume_map = {}

    for chunk in chunks:

        source = chunk.metadata.get(
            "source"
        )

        if source not in resume_map:

            resume_map[source] = ""

        resume_map[source] += (
            "\n"
            + chunk.page_content
        )

    resume_metadata = {}

    for source, text in resume_map.items():

        resume_metadata[source] = (
            extract_metadata(text)
        )

    for chunk in chunks:

        source = chunk.metadata.get(
            "source"
        )

        chunk.metadata.update(
            resume_metadata[source]
        )

        processed_chunks.append(chunk)

    vectordb = Chroma.from_documents(
        documents=processed_chunks,
        embedding=embedding,
        persist_directory=DB_DIR
    )

    print(
        "\n✅ Vector DB created successfully!"
    )


if __name__ == "__main__":

    print("\nLoading resumes...")

    docs = load_documents(
        RESUME_FOLDER
    )

    print("\nChunking resumes...")

    chunks = chunk_documents(docs)

    print("\nCreating Vector DB...")

    create_vector_db(chunks)