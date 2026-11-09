"""Tests for filesystem MCP tools, resources, and the HTTP client connection."""

import asyncio
import json
import os
import subprocess
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

import filesystem_mcp_server as server
from tools.mcp_client import (
    batch_read_resumes,
    call_mcp_tool,
    list_resume_files,
    watch_resume_directory,
)


class FilesystemMcpServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name).resolve()
        self.environment = patch.dict(os.environ, {"RESUME_DIRECTORY": str(self.root)})
        self.environment.start()
        self.previous_snapshot = server._directory_snapshots.get(str(self.root))
        server._directory_snapshots[str(self.root)] = set()

    def tearDown(self):
        if self.previous_snapshot is None:
            server._directory_snapshots.pop(str(self.root), None)
        else:
            server._directory_snapshots[str(self.root)] = self.previous_snapshot
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_filesystem_tools_and_configuration_resource(self):
        (self.root / "engineer.txt").write_text(
            "Python and cloud experience", encoding="utf-8"
        )

        config = server.get_server_config()
        listing = server.list_files()
        content = server.read_file("engineer.txt")
        search = server.search_in_file("engineer.txt", "python")
        written = server.write_file("new/note.txt", "Created through MCP")

        self.assertEqual(config["resume_directory"], str(self.root))
        self.assertEqual([item["name"] for item in listing], ["engineer.txt"])
        self.assertIn("Python", content["content"])
        self.assertEqual(search["count"], 1)
        self.assertTrue(written["success"])
        self.assertTrue((self.root / "new" / "note.txt").is_file())
        self.assertEqual(
            json.loads(server.configuration_resource())["resume_directory"],
            str(self.root),
        )

    def test_batch_processing_returns_file_errors_without_dropping_good_files(self):
        (self.root / "good.txt").write_text("Python engineer", encoding="utf-8")
        (self.root / "bad.pdf").write_bytes(b"not a valid PDF")

        result = server.batch_process(max_workers=2)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["files"][0]["metadata"]["name"], "good.txt")
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(Path(result["errors"][0]["path"]).name, "bad.pdf")

    def test_paths_cannot_escape_the_configured_resume_directory(self):
        with self.assertRaises(ValueError):
            server.read_file("../outside.txt")
        with self.assertRaises(ValueError):
            server.write_file(str(self.root.parent / "outside.txt"), "not allowed")

    def test_watch_directory_reports_a_new_resume(self):
        (self.root / "new_resume.txt").write_text("New candidate", encoding="utf-8")

        result = server.watch_directory(timeout_seconds=0)

        self.assertEqual(result["count"], 1)
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["files"][0]["metadata"]["name"], "new_resume.txt")

    def test_http_client_discovers_resources_and_calls_jsonrpc_tools(self):
        (self.root / "candidate.txt").write_text("Python developer", encoding="utf-8")

        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        server_url = f"http://127.0.0.1:{port}/mcp"
        environment = os.environ.copy()
        environment.update(
            {
                "RESUME_DIRECTORY": str(self.root),
                "FASTMCP_HOST": "127.0.0.1",
                "FASTMCP_PORT": str(port),
            }
        )
        process = subprocess.Popen(
            [sys.executable, str(Path(server.__file__).resolve())],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    self.fail("MCP server exited before accepting HTTP connections.")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                self.fail("MCP server did not start listening within 10 seconds.")

            with patch.dict(os.environ, {"MCP_SERVER_URL": server_url}):
                files = list_resume_files(str(self.root))
                batch = batch_read_resumes(str(self.root))
                (self.root / "new_candidate.txt").write_text(
                    "New Python developer", encoding="utf-8"
                )
                watched = watch_resume_directory(
                    str(self.root),
                    interval_seconds=0.1,
                    timeout_seconds=1,
                )

                async def discover():
                    async with streamable_http_client(server_url) as (
                        read_stream,
                        write_stream,
                        _,
                    ):
                        async with ClientSession(read_stream, write_stream) as session:
                            await session.initialize()
                            tools = await session.list_tools()
                            resources = await session.list_resources()
                            templates = await session.list_resource_templates()
                    return tools.tools, resources.resources, templates.resourceTemplates

                tools, resources, templates = asyncio.run(discover())

                self.assertEqual([item["name"] for item in files], ["candidate.txt"])
                self.assertEqual(batch["count"], 1)
                self.assertEqual(watched["count"], 1)
                self.assertEqual(
                    watched["files"][0]["metadata"]["name"], "new_candidate.txt"
                )
                self.assertTrue(
                    {
                        "get_server_config", "list_files", "read_file", "write_file",
                        "search_in_file", "batch_process", "watch_directory",
                    }.issubset({item.name for item in tools})
                )
                self.assertIn("filesystem://config", [str(item.uri) for item in resources])
                self.assertIn(
                    "filesystem://resumes/{filename}",
                    [str(item.uriTemplate) for item in templates],
                )
                with self.assertRaises(RuntimeError):
                    call_mcp_tool("read_file", {"filepath": "../outside.txt"})
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
