"""Tests for the SQLite-backed interview question-bank MCP resource."""

import json
import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import interview_mcp_server as server
from tools.mcp_client import get_interview_questions


class InterviewMcpServerTests(unittest.TestCase):
    def test_resource_returns_skill_indexed_questions(self):
        payload = json.loads(server.question_bank_resource())
        catalog = json.loads(server.skills_resource())

        self.assertEqual(payload["source"], "SQLite interview question bank")
        self.assertIn("python", payload["questions"])
        self.assertTrue(payload["questions"]["python"])
        self.assertIn(
            {"name": "python", "question_count": 1},
            catalog["skills"],
        )

    def test_client_reads_and_filters_resource_from_running_server(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        server_url = f"http://127.0.0.1:{port}/mcp"
        environment = os.environ.copy()
        environment.update(
            {
                "INTERVIEW_MCP_HOST": "127.0.0.1",
                "INTERVIEW_MCP_PORT": str(port),
            }
        )
        process = subprocess.Popen(
            [sys.executable, str(Path(server.__file__).resolve())],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    self.fail("Interview MCP server exited before accepting connections.")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                self.fail("Interview MCP server did not start within 20 seconds.")

            with patch.dict(
                os.environ, {"INTERVIEW_MCP_SERVER_URL": server_url}
            ):
                questions = get_interview_questions(["Python"])

            self.assertEqual(set(questions), {"python", "general"})
            self.assertTrue(any("Python" in question for question in questions["python"]))
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
