"""Synchronous bridge from the LangGraph nodes to the filesystem MCP server."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


DEFAULT_MCP_SERVER_URL = "http://127.0.0.1:8000/mcp"


async def _call_tool(
    name: str,
    arguments: dict[str, Any],
) -> Any:
    server_url = os.environ.get("MCP_SERVER_URL", DEFAULT_MCP_SERVER_URL)
    async with streamable_http_client(server_url) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            await session.list_resources()
            await session.list_resource_templates()
            result = await session.call_tool(name, arguments)

    if result.isError:
        details = [
            item.text for item in result.content
            if getattr(item, "text", None)
        ]
        raise RuntimeError(f"MCP tool {name!r} failed: {'; '.join(details)}")
    if result.structuredContent is not None:
        structured = result.structuredContent
        if isinstance(structured, dict) and set(structured) == {"result"}:
            return structured["result"]
        return structured

    text = "\n".join(
        item.text for item in result.content if getattr(item, "text", None)
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def call_mcp_tool(
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Connect to the configured Streamable HTTP MCP server and call a tool."""
    return asyncio.run(_call_tool(name, arguments))


def list_resume_files(
    directory: str,
    extension: str | None = None,
) -> list[dict[str, Any]]:
    """List resume files through the filesystem MCP server."""
    normalized_directory = str(Path(directory).expanduser().resolve())
    return call_mcp_tool(
        "list_files",
        {"directory": normalized_directory, "extension": extension},
    )


def batch_read_resumes(directory: str) -> dict[str, Any]:
    """Read all supported resumes through one MCP batch request."""
    normalized_directory = str(Path(directory).expanduser().resolve())
    return call_mcp_tool(
        "batch_process",
        {"directory": normalized_directory},
    )


def watch_resume_directory(
    directory: str,
    interval_seconds: float = 1.0,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Wait for new supported resumes through the filesystem MCP server."""
    normalized_directory = str(Path(directory).expanduser().resolve())
    return call_mcp_tool(
        "watch_directory",
        {
            "directory": normalized_directory,
            "interval_seconds": interval_seconds,
            "timeout_seconds": timeout_seconds,
        },
    )


async def _read_interview_question_bank(server_url: str) -> dict[str, Any]:
    async with streamable_http_client(server_url) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            resources = await session.list_resources()
            await session.list_resource_templates()
            resource_uris = {
                "interview-db://skills",
                "interview-db://question-bank",
            }
            available_uris = {str(item.uri) for item in resources.resources}
            if not resource_uris.issubset(available_uris):
                missing = ", ".join(sorted(resource_uris - available_uris))
                raise RuntimeError(
                    f"Interview MCP server is missing resources: {missing}."
                )
            results = {
                uri: await session.read_resource(uri)
                for uri in sorted(resource_uris)
            }

    payloads = {}
    for uri, result in results.items():
        text = "\n".join(
            item.text for item in result.contents if getattr(item, "text", None)
        )
        try:
            payloads[uri] = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Interview MCP resource {uri!r} returned invalid JSON."
            ) from exc

    question_bank = payloads["interview-db://question-bank"]
    catalog = payloads["interview-db://skills"]
    if not isinstance(question_bank, dict) or not isinstance(
        question_bank.get("questions"), dict
    ):
        raise RuntimeError("Interview question-bank resource has an invalid shape.")
    if not isinstance(catalog, dict) or not isinstance(catalog.get("skills"), list):
        raise RuntimeError("Interview skills resource has an invalid shape.")
    return {"questions": question_bank["questions"], "skills": catalog["skills"]}


def get_interview_questions(
    skills: list[str],
    server_url: str | None = None,
) -> dict[str, list[str]]:
    """Read relevant question lists from the additional SQLite MCP resource."""
    url = server_url or os.environ.get(
        "INTERVIEW_MCP_SERVER_URL", "http://127.0.0.1:8001/mcp"
    )
    payload = asyncio.run(_read_interview_question_bank(url))
    available = payload["questions"]
    wanted = {skill.casefold() for skill in skills}
    wanted.add("general")
    catalog_skills = {
        entry["name"].casefold()
        for entry in payload["skills"]
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    wanted.intersection_update(catalog_skills)
    return {
        skill: questions
        for skill, questions in available.items()
        if skill.casefold() in wanted and isinstance(questions, list)
    }
