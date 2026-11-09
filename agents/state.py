"""Typed data shared by the LangGraph workflow and chat interface."""

from typing import Any, TypedDict


class AgentState(TypedDict):
    """Keep the conversation, active criteria, candidates, and reports."""

    messages: list[str]
    job_description: str
    requirements: dict[str, Any]
    candidates: list[Any]
    rankings: list[dict[str, Any]]
    feedback: str
    final_report: str
