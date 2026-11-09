import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import rag_tools
from tools.fs_tools import list_files, read_file


class RagSkillSearchTests(unittest.TestCase):
    def test_java_search_uses_exact_skill_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "java.txt").write_text("Engineer with Java experience.", encoding="utf-8")
            (root / "javascript.txt").write_text(
                "Engineer with JavaScript experience only.", encoding="utf-8"
            )
            (root / "python.txt").write_text(
                "Engineer with Python experience.", encoding="utf-8"
            )

            with patch.object(rag_tools, "RESUME_FOLDER", root):
                java_results = rag_tools.semantic_search("Java")
                python_results = rag_tools.semantic_search("Python")

        self.assertEqual(
            [Path(document.metadata["source"]).name for document, _ in java_results],
            ["java.txt"],
        )
        self.assertEqual(
            [Path(document.metadata["source"]).name for document, _ in python_results],
            ["python.txt"],
        )

    def test_skill_search_finds_every_resume_in_the_folder(self) -> None:
        files = list_files(str(rag_tools.RESUME_FOLDER))
        for skill in ("Java", "Python"):
            expected = set()
            for metadata in files:
                result = read_file(metadata["path"])
                self.assertTrue(result["success"], result.get("error"))
                if re.search(
                    rf"(?<![a-z0-9]){skill}(?![a-z0-9])",
                    result["content"],
                    re.IGNORECASE,
                ):
                    expected.add(Path(metadata["path"]).name)

            results = rag_tools.semantic_search(skill, k=1000)
            actual = {
                Path(document.metadata["source"]).name
                for document, _ in results
            }
            self.assertEqual(actual, expected)

    def test_empty_vector_index_uses_local_search_without_loading_embeddings(self) -> None:
        with patch.object(
            rag_tools,
            "HuggingFaceEmbeddings",
            side_effect=AssertionError("Empty-index search should not load a model"),
        ):
            results = rag_tools.semantic_search(" ", k=1000)

        self.assertEqual(len(results), rag_tools.count_resumes())


if __name__ == "__main__":
    unittest.main()
