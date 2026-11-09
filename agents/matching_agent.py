"""LangGraph nodes and the stateful conversational entry point."""

import copy

from agents.conversation import identify_intent, requested_count
from agents.reporting import (
    build_comparison_report,
    build_ranking_explanation,
    build_search_report,
    explain_ranking_changes,
)
from agents.screening import (
    build_deep_analysis,
    build_final_decisions,
    build_screening_questions,
)
from tools.mcp_client import get_interview_questions
from tools.matching_tools import extract_requirements, rank_candidates
from tools.rag_tools import count_resumes, semantic_search


def parse_jd(state):
    """Record that the current user request has entered the workflow."""
    state["messages"].append("Job description received")
    return state


def extract_req_node(state):
    """Extract skills and experience, applying feedback to previous criteria."""
    print("\n[Agent] Extracting job requirements...")
    previous = state.get("requirements") or None
    feedback = state.get("feedback", "")

    state["requirements"] = extract_requirements(
        state["job_description"],
        previous=previous if feedback else None,
        feedback=feedback,
    )
    state["messages"].append("Requirements extracted")
    return state


def search_resumes_node(state):
    """Search the resume collection broadly before creating the top-ten screen."""
    print("\n[Agent] Searching resumes through the filesystem MCP server...")
    if state.get("feedback"):
        active_skills = (
            state["requirements"].get("must_have_skills", [])
            + state["requirements"].get("preferred_skills", [])
        )
        query = " ".join(active_skills)
        if state["requirements"].get("experience"):
            query += f" {state['requirements']['experience']} years experience"
    else:
        query = state["job_description"]

    state["candidates"] = semantic_search(
        query,
        k=1000,
    )
    state["messages"].append(
        f"Retrieved {len(state['candidates'])} resume documents or sections via MCP"
    )
    return state


def rank_candidates_node(state):
    """Rank the initial candidate pool and retain the requested shortlist."""
    print("\n[Agent] Ranking candidates...")
    count = requested_count(state["job_description"], default=10)
    state["rankings"] = rank_candidates(
        state["candidates"],
        state["requirements"],
        top_k=count,
    )
    state["messages"].append(f"Ranked the top {len(state['rankings'])} candidates")
    return state


def generate_report_node(state):
    """Create the explainable first-round report."""
    print("\n[Agent] Generating the initial screening report...")
    state["final_report"] = build_search_report(
        state["rankings"],
        resume_count=count_resumes(),
    )
    state["messages"].append("Initial screening report generated")
    return state


def _new_state(message):
    """Create empty conversation state for a new job search."""
    return {
        "messages": [f"User: {message}"],
        "job_description": message,
        "requirements": {},
        "candidates": [],
        "rankings": [],
        "feedback": "",
        "final_report": "",
    }


def _get_graph():
    """Build the LangGraph workflow when a search is first requested."""
    from agents.graph_builder import build_graph

    return build_graph()


def run_agent(message, existing_state=None, interview_mcp_url=None):
    """Handle a new search or a follow-up using the active conversation state."""
    intent = identify_intent(message, bool(existing_state and existing_state["rankings"]))

    if not existing_state or intent == "search":
        state = _get_graph().invoke(_new_state(message))
        return state

    state = copy.deepcopy(existing_state)
    state["messages"].append(f"User: {message}")

    if intent == "compare":
        count = requested_count(message, default=3)
        if count > len(state["rankings"]) and state.get("candidates"):
            state["rankings"] = rank_candidates(
                state["candidates"],
                state["requirements"],
                top_k=count,
            )
        state["final_report"] = build_comparison_report(message, state["rankings"])
        state["messages"].append("Compared candidates")
        return state

    if intent == "explain":
        state["final_report"] = build_ranking_explanation(message, state["rankings"])
        state["messages"].append("Explained the candidate ranking")
        return state

    if intent == "screening_questions":
        state["final_report"] = build_screening_questions(
            state["job_description"],
            state["requirements"],
        )
        if interview_mcp_url:
            skills = (
                state["requirements"].get("must_have_skills", [])
                + state["requirements"].get("preferred_skills", [])
            )
            question_bank = get_interview_questions(skills, interview_mcp_url)
            bank_questions = [
                (skill, question)
                for skill, questions in question_bank.items()
                for question in questions
            ]
            if bank_questions:
                state["final_report"] += "\n\n# ADDITIONAL QUESTIONS FROM MCP QUESTION BANK\n"
                state["final_report"] += "\n".join(
                    f"- [{skill}] {question}" for skill, question in bank_questions
                )
        state["messages"].append("Created questions from the active job description")
        if interview_mcp_url:
            state["messages"].append(
                "Read the SQLite interview question-bank MCP resource"
            )
        return state

    if intent == "deep_analysis":
        count = requested_count(message, default=10)
        state["final_report"] = build_deep_analysis(state["rankings"][:count])
        state["messages"].append("Completed second-round candidate analysis")
        return state

    if intent == "final_decision":
        state["final_report"] = build_final_decisions(state["rankings"])
        state["messages"].append("Generated final hire/no-hire decisions")
        return state

    if intent == "refine":
        old_rankings = copy.deepcopy(state["rankings"])
        state["job_description"] = (
            f"{state['job_description']}\n\nAdditional criteria: {message}"
        )
        state["feedback"] = message
        state = _get_graph().invoke(state)
        state["final_report"] += "\n\n" + explain_ranking_changes(
            old_rankings,
            state["rankings"],
        )
        return state

    state = _get_graph().invoke(_new_state(message))
    return state
