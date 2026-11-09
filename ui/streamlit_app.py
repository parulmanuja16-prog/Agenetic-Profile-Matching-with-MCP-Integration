"""Streamlit chat interface for the resume-matching agent."""

import os
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.matching_agent import run_agent
from tools.mcp_client import batch_read_resumes, watch_resume_directory
from tools.rag_tools import RESUME_FOLDER, count_resumes


DEFAULT_INTERVIEW_MCP_URL = os.environ.get(
    "INTERVIEW_MCP_SERVER_URL", "http://127.0.0.1:8001/mcp"
)


def _start_conversation():
    """Create empty UI history and agent state for a new conversation."""
    st.session_state.chat_history = []
    st.session_state.agent_state = None


def _show_sidebar():
    """Show resume count, example questions, and a reset button."""
    with st.sidebar:
        st.header("Resume collection")
        st.metric("Supported resumes", count_resumes())
        st.caption("PDF, TXT, and DOCX files in `data/resumes/`.")
        st.divider()
        st.subheader("Try asking")
        st.markdown(
            "- Find React candidates with 3+ years experience\n"
            "- Compare the top 3 matches\n"
            "- Why did Alice rank higher than Bob?\n"
            "- Prioritize Python\n"
            "- Create screening questions\n"
            "- Run deep analysis\n"
            "- Give final hire/no-hire recommendations"
        )
        if st.button("Start a new conversation", use_container_width=True):
            _start_conversation()
            st.rerun()

        st.divider()
        st.subheader("MCP resume operations")
        if st.button("Batch process resumes", use_container_width=True):
            with st.spinner("Reading supported resumes through MCP..."):
                st.session_state.batch_result = batch_read_resumes(
                    str(RESUME_FOLDER)
                )

        if "batch_result" in st.session_state:
            batch = st.session_state.batch_result
            if batch["errors"]:
                st.warning(
                    f"Processed {batch['count']} resume(s); "
                    f"{len(batch['errors'])} file(s) could not be read."
                )
            else:
                st.success(f"Processed {batch['count']} resume(s).")
            with st.expander("Batch results"):
                for item in batch["files"]:
                    metadata = item["metadata"]
                    st.write(
                        f"{metadata['name']} "
                        f"({metadata.get('extension', 'supported file')})"
                    )
                for error in batch["errors"]:
                    st.error(f"{error['path']}: {error['error']}")

        st.caption(
            "Wait for supported resume files added after the MCP server starts."
        )
        watch_interval = st.number_input(
            "Check interval (seconds)",
            min_value=0.1,
            max_value=60.0,
            value=1.0,
            step=0.1,
            key="watch_interval_seconds",
        )
        watch_timeout = st.number_input(
            "Watch timeout (seconds)",
            min_value=0.0,
            max_value=300.0,
            value=30.0,
            step=1.0,
            key="watch_timeout_seconds",
        )
        if st.button("Watch for new resumes", use_container_width=True):
            with st.spinner("Watching the resume directory through MCP..."):
                st.session_state.watch_result = watch_resume_directory(
                    str(RESUME_FOLDER),
                    interval_seconds=watch_interval,
                    timeout_seconds=watch_timeout,
                )

        if "watch_result" in st.session_state:
            watched = st.session_state.watch_result
            if watched["timed_out"]:
                st.info("No new resumes were found before the watch timed out.")
            else:
                st.success(f"Found {watched['count']} new resume(s).")
                with st.expander("New resume results"):
                    for item in watched["files"]:
                        st.write(item["metadata"]["name"])

        st.divider()
        st.subheader("Additional MCP server")
        use_interview_mcp = st.checkbox(
            "Use SQLite interview question bank",
            key="use_interview_mcp",
            help=(
                "For screening-question requests, the agent reads the "
                "interview-db://skills and interview-db://question-bank resources "
                "from a second MCP server."
            ),
        )
        if use_interview_mcp:
            st.text_input(
                "Interview MCP server URL",
                value=DEFAULT_INTERVIEW_MCP_URL,
                key="interview_mcp_server_url",
            )


def _show_chat_history():
    """Render saved user and assistant messages in chronological order."""
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def _process_user_message(message):
    """Run one user turn and save the agent response for the chat display."""
    st.session_state.chat_history.append(
        {"role": "user", "content": message}
    )
    with st.chat_message("user"):
        st.markdown(message)

    with st.chat_message("assistant"):
        with st.spinner("Searching resumes and preparing a response..."):
            interview_mcp_url = None
            if st.session_state.get("use_interview_mcp", False):
                interview_mcp_url = st.session_state.get(
                    "interview_mcp_server_url", DEFAULT_INTERVIEW_MCP_URL
                )
            try:
                result = run_agent(
                    message,
                    st.session_state.agent_state,
                    interview_mcp_url=interview_mcp_url,
                )
            except RuntimeError as exc:
                error = f"Unable to complete the request: {exc}"
                st.error(error)
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": error}
                )
                return
        st.markdown(result["final_report"])

    st.session_state.agent_state = result
    st.session_state.chat_history.append(
        {"role": "assistant", "content": result["final_report"]}
    )


def main():
    """Display the chat interface and handle submitted messages."""
    st.set_page_config(
        page_title="Agentic Profile Matching",
        page_icon="👥",
        layout="wide",
    )
    st.title("Agentic Profile Matching")
    st.write(
        "Search resumes, refine the criteria, compare candidates, "
        "and review explainable screening reports."
    )

    if "chat_history" not in st.session_state:
        _start_conversation()

    _show_sidebar()
    _show_chat_history()

    prompt = st.chat_input(
        "Describe the role or ask a follow-up about the current shortlist"
    )
    if prompt:
        _process_user_message(prompt.strip())


if __name__ == "__main__":
    main()
