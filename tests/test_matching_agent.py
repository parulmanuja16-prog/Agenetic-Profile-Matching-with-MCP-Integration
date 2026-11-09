"""Tests for conversation handling, ranking rounds, and readable reports."""

import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from agents.matching_agent import run_agent
from tools.matching_tools import extract_requirements, rank_candidates


class MatchingConversationTests(unittest.TestCase):
    """Check that the chat interface retains and updates candidate context."""

    def setUp(self):
        """Create an independent pair of sample candidates for each test."""
        self.documents = [
            (
                Document(
                    page_content=(
                        "John Smith\nSkills: React, Python\n"
                        "5 years experience building web applications."
                    ),
                    metadata={"name": "John Smith", "experience_years": 5, "source": "john.txt"},
                ),
                0.1,
            ),
            (
                Document(
                    page_content=(
                        "Jane Doe\nSkills: React\n"
                        "2 years experience building web applications."
                    ),
                    metadata={"name": "Jane Doe", "experience_years": 2, "source": "jane.txt"},
                ),
                0.2,
            ),
        ]

    def test_requirements_separate_preferred_skills_from_must_haves(self):
        """Understand required skills, preferred skills, and experience."""
        requirements = extract_requirements(
            "React required, prioritize Python, and at least 3 years experience"
        )

        self.assertIn("react", requirements["must_have_skills"])
        self.assertIn("python", requirements["preferred_skills"])
        self.assertEqual(requirements["experience"], 3)

    def test_search_compare_explain_refine_and_screening_rounds(self):
        """Keep results between turns and respond to common follow-up intents."""
        with patch("agents.matching_agent.semantic_search", return_value=self.documents):
            state = run_agent("Find React candidates with 3+ years experience")

            self.assertEqual(len(state["rankings"]), 2)
            self.assertIn("INITIAL SCREEN", state["final_report"])
            self.assertIn("Strengths:", state["final_report"])
            self.assertIn("Gaps:", state["final_report"])
            self.assertNotIn("hire", state["final_report"].casefold())
            self.assertNotIn("recommendation", state["final_report"].casefold())

            comparison = run_agent("Compare the top 2 matches side by side", state)
            self.assertIn("SIDE-BY-SIDE COMPARISON", comparison["final_report"])
            self.assertIn("John Smith", comparison["final_report"])
            self.assertIn("Jane Doe", comparison["final_report"])

            explanation = run_agent("Why did John rank higher than Jane?", comparison)
            self.assertIn("John Smith scored", explanation["final_report"])
            self.assertIn("Jane Doe scored", explanation["final_report"])

            refined = run_agent("Prioritize Python and lower experience to 2 years", explanation)
            self.assertIn("python", refined["requirements"]["preferred_skills"])
            self.assertEqual(refined["requirements"]["experience"], 2)
            self.assertIn("RANKING CHANGES", refined["final_report"])

            deep_analysis = run_agent("Run deep analysis on the top 2", refined)
            self.assertIn("SECOND-ROUND DEEP ANALYSIS", deep_analysis["final_report"])
            self.assertNotIn("hire", deep_analysis["final_report"].casefold())
            self.assertNotIn("recommendation", deep_analysis["final_report"].casefold())

            final_decision = run_agent("Give final hire/no-hire recommendation", deep_analysis)
            self.assertIn("FINAL HIRING RECOMMENDATIONS", final_decision["final_report"])
            self.assertIn("Decision:", final_decision["final_report"])

            relaxed = run_agent("Remove React and Python", final_decision)
            self.assertEqual(relaxed["requirements"]["must_have_skills"], [])
            self.assertEqual(relaxed["requirements"]["preferred_skills"], [])

    def test_screening_questions_can_include_additional_mcp_resources(self):
        with patch("agents.matching_agent.semantic_search", return_value=self.documents):
            state = run_agent("Find React candidates")

        with patch(
            "agents.matching_agent.get_interview_questions",
            return_value={
                "react": ["How do you manage React component state?"],
                "general": ["Describe a technical trade-off."],
            },
        ) as get_questions:
            result = run_agent(
                "Create screening questions",
                state,
                interview_mcp_url="http://127.0.0.1:8001/mcp",
            )

        get_questions.assert_called_once_with(
            ["react"], "http://127.0.0.1:8001/mcp"
        )
        self.assertIn("ADDITIONAL QUESTIONS FROM MCP QUESTION BANK", result["final_report"])
        self.assertIn("How do you manage React component state?", result["final_report"])
        self.assertIn("Describe a technical trade-off.", result["final_report"])

    def test_comparative_preference_reorders_candidates(self):
        """Prefer the first skill in an 'X over Y' refinement."""
        results = [
            (
                Document(
                    page_content="Anika Taylor\nSkills: Java, Spring Boot\n5 years experience",
                    metadata={
                        "name": "Anika Taylor",
                        "experience_years": 5,
                        "source": "anika.txt",
                    },
                ),
                0.05,
            ),
            (
                Document(
                    page_content="Bobby Chen\nSkills: JavaScript, React\n4 years experience",
                    metadata={
                        "name": "Bobby Chen",
                        "experience_years": 4,
                        "source": "bobby.txt",
                    },
                ),
                0.15,
            ),
        ]

        with patch("agents.matching_agent.semantic_search", return_value=results):
            state = run_agent("Find a Java developer")
            self.assertEqual(state["rankings"][0]["name"], "Anika Taylor")

            refined = run_agent("Prefer JavaScript over Java", state)

        self.assertEqual(refined["requirements"]["preferred_skills"], ["javascript"])
        self.assertNotIn("java", refined["requirements"]["must_have_skills"])
        self.assertEqual(refined["rankings"][0]["name"], "Bobby Chen")
        self.assertNotIn("javascript", refined["rankings"][1]["skills"])

    def test_initial_screen_returns_top_ten_from_one_hundred(self):
        """Limit first-round output to ten after considering a 100-resume pool."""
        documents = [
            (
                Document(
                    page_content=f"Candidate {number}\nPython developer",
                    metadata={
                        "name": f"Candidate {number}",
                        "experience_years": number % 8,
                        "source": f"candidate_{number}.txt",
                    },
                ),
                number / 100,
            )
            for number in range(100)
        ]
        requirements = extract_requirements("Python developer")

        rankings = rank_candidates(documents, requirements, top_k=10)

        self.assertEqual(len(rankings), 10)


if __name__ == "__main__":
    unittest.main()
