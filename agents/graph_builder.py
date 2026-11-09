"""Connect the resume-matching stages into a LangGraph workflow."""

from langgraph.graph import END, StateGraph

from agents.matching_agent import (
    extract_req_node,
    generate_report_node,
    parse_jd,
    rank_candidates_node,
    search_resumes_node,
)
from agents.state import AgentState


def build_graph():
    """Build and compile the first-round resume screening graph."""
    workflow = StateGraph(AgentState)
    workflow.add_node("parse_jd", parse_jd)
    workflow.add_node("extract_requirements", extract_req_node)
    workflow.add_node("search_resumes", search_resumes_node)
    workflow.add_node("rank_candidates", rank_candidates_node)
    workflow.add_node("generate_report", generate_report_node)

    workflow.set_entry_point("parse_jd")
    workflow.add_edge("parse_jd", "extract_requirements")
    workflow.add_edge("extract_requirements", "search_resumes")
    workflow.add_edge("search_resumes", "rank_candidates")
    workflow.add_edge("rank_candidates", "generate_report")
    workflow.add_edge("generate_report", END)
    return workflow.compile()
