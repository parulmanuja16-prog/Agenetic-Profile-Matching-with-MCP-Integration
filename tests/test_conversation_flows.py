"""Conversation scenarios for the terminal and Streamlit agent interfaces."""

import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from agents.matching_agent import run_agent


class ConversationFlowTests(unittest.TestCase):
    """Test six common conversations without loading the vector database."""

    def setUp(self):
        """Create sample resume results and replace external search calls."""
        self.search_results = [
            (
                Document(
                    page_content=(
                        "Alice Johnson\nSkills: React, Python, Docker\n"
                        "5 years experience building web applications."
                    ),
                    metadata={
                        "name": "Alice Johnson",
                        "experience_years": 5,
                        "source": "alice.txt",
                    },
                ),
                0.1,
            ),
            (
                Document(
                    page_content=(
                        "Bob Chen\nSkills: React, Java\n"
                        "4 years experience building web applications."
                    ),
                    metadata={
                        "name": "Bob Chen",
                        "experience_years": 4,
                        "source": "bob.txt",
                    },
                ),
                0.2,
            ),
            (
                Document(
                    page_content=(
                        "Jane Doe\nSkills: Java, Python\n"
                        "2 years experience building data applications."
                    ),
                    metadata={
                        "name": "Jane Doe",
                        "experience_years": 2,
                        "source": "jane.txt",
                    },
                ),
                0.3,
            ),
        ]
        self.search_patch = patch(
            "agents.matching_agent.semantic_search",
            return_value=self.search_results,
        )
        self.count_patch = patch(
            "agents.matching_agent.count_resumes",
            return_value=len(self.search_results),
        )
        self.search_patch.start()
        self.count_patch.start()
        self.addCleanup(self.search_patch.stop)
        self.addCleanup(self.count_patch.stop)

    def _start_search(self):
        """Begin the common search used by the follow-up scenarios."""
        return run_agent("Find React candidates with 3+ years experience")

    def test_flow_one_starts_a_job_search(self):
        """Return a first-round report and save the shortlist."""
        state = self._start_search()

        self.assertIn("INITIAL SCREEN", state["final_report"])
        self.assertEqual(len(state["rankings"]), 3)
        self.assertEqual(state["requirements"]["experience"], 3)

    def test_flow_two_compares_the_top_three(self):
        """Compare candidate scores in a readable table."""
        state = self._start_search()
        state = run_agent("Compare the top 3 matches side by side", state)

        self.assertIn("SIDE-BY-SIDE COMPARISON", state["final_report"])
        self.assertIn("Alice Johnson", state["final_report"])
        self.assertIn("Bob Chen", state["final_report"])
        self.assertIn("Jane Doe", state["final_report"])

    def test_comparison_expands_shortlist_for_spelled_out_top_four(self):
        """Honor a top-four request even when the initial screen held three."""
        for name, years, source in [
            ("Chris Lee", 6, "chris.txt"),
            ("Morgan Ray", 4, "morgan.txt"),
        ]:
            self.search_results.append((
                Document(
                    page_content=(
                        f"{name}\nSkills: React, Python\n"
                        f"{years} years experience building web applications."
                    ),
                    metadata={
                        "name": name,
                        "experience_years": years,
                        "source": source,
                    },
                ),
                0.4,
            ))

        state = run_agent("Find top 3 React candidates", None)
        self.assertEqual(len(state["rankings"]), 3)

        state = run_agent("Compare the top four matches", state)

        candidate_rows = [
            line for line in state["final_report"].splitlines()
            if line.startswith("| ") and not line.startswith("| Candidate")
        ]
        self.assertEqual(len(candidate_rows), 4)
        self.assertEqual(len(state["rankings"]), 4)

    def test_flow_three_explains_two_named_candidates(self):
        """Explain the actual scores for candidates named by the user."""
        state = self._start_search()
        state = run_agent("Why did Bob rank higher than Jane?", state)

        self.assertIn("Bob Chen scored", state["final_report"])
        self.assertIn("Jane Doe scored", state["final_report"])

    def test_flow_four_refines_criteria_and_reports_changes(self):
        """Apply a new must-have skill and minimum experience."""
        state = self._start_search()
        state = run_agent("Add Python as required and raise the minimum to 5 years", state)

        self.assertIn("python", state["requirements"]["must_have_skills"])
        self.assertEqual(state["requirements"]["experience"], 5)
        self.assertIn("RANKING CHANGES", state["final_report"])

    def test_flow_five_runs_second_round_analysis(self):
        """Create detailed evidence reports from the current shortlist."""
        state = self._start_search()
        state = run_agent("Run deep analysis on the top 2", state)

        self.assertIn("SECOND-ROUND DEEP ANALYSIS", state["final_report"])
        self.assertIn("Strengths:", state["final_report"])
        self.assertIn("Gaps:", state["final_report"])

    def test_flow_six_returns_final_hire_decisions(self):
        """Make final rule-based decisions for the shortlisted candidates."""
        state = self._start_search()
        state = run_agent("Give a final hire or no hire recommendation", state)

        self.assertIn("FINAL HIRING RECOMMENDATIONS", state["final_report"])
        self.assertIn("Decision:", state["final_report"])

    def test_flow_seven_creates_questions_from_the_active_job_description(self):
        """Create role-screening questions from the current job criteria."""
        state = self._start_search()
        state = run_agent("Create screening questions", state)

        self.assertIn("SCREENING QUESTIONS", state["final_report"])
        self.assertIn("React", state["final_report"])
        self.assertIn("3 years", state["final_report"])
        self.assertNotIn("hire", state["final_report"].casefold())
        self.assertEqual(len(state["rankings"]), 3)


if __name__ == "__main__":
    unittest.main()
