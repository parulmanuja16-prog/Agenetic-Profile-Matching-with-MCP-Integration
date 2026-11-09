"""SQLite-backed MCP resource for role-specific technical interview questions."""

from __future__ import annotations

import json
import os
import sqlite3
from threading import Lock

from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "interview-question-bank",
    host=os.environ.get("INTERVIEW_MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("INTERVIEW_MCP_PORT", "8001")),
)

_database = sqlite3.connect(":memory:", check_same_thread=False)
_database.row_factory = sqlite3.Row
_database_lock = Lock()
_database.execute(
    """
    CREATE TABLE questions (
        skill TEXT NOT NULL,
        question TEXT NOT NULL,
        PRIMARY KEY (skill, question)
    )
    """
)
_database.executemany(
    "INSERT INTO questions (skill, question) VALUES (?, ?)",
    [
        ("aws", "How would you design a highly available service on AWS?"),
        ("docker", "How do you make a Docker image reproducible and secure?"),
        ("general", "Describe a technical decision you made and its trade-offs."),
        ("general", "How do you investigate a production issue and prevent recurrence?"),
        ("java", "How do you manage concurrency and resource lifecycles in Java?"),
        ("machine learning", "How would you evaluate a model beyond its training metrics?"),
        ("python", "How do you structure and test a maintainable Python service?"),
        ("react", "How do you manage state and prevent unnecessary React renders?"),
        ("sql", "How would you diagnose and improve a slow SQL query?"),
    ],
)
_database.commit()


@mcp.resource("interview-db://question-bank")
def question_bank_resource() -> str:
    """Return skill-indexed interview questions from the SQLite question bank."""
    with _database_lock:
        rows = _database.execute(
            "SELECT skill, question FROM questions ORDER BY skill, question"
        ).fetchall()
    questions: dict[str, list[str]] = {}
    for row in rows:
        questions.setdefault(row["skill"], []).append(row["question"])
    return json.dumps(
        {"source": "SQLite interview question bank", "questions": questions},
        indent=2,
    )


@mcp.resource("interview-db://skills")
def skills_resource() -> str:
    """Return skill names and question counts from the SQLite question bank."""
    with _database_lock:
        rows = _database.execute(
            "SELECT skill, COUNT(*) AS question_count "
            "FROM questions GROUP BY skill ORDER BY skill"
        ).fetchall()
    return json.dumps(
        {
            "skills": [
                {"name": row["skill"], "question_count": row["question_count"]}
                for row in rows
            ]
        },
        indent=2,
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
