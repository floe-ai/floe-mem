from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class SkillScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.memory_tool = cls.repo_root / "skills" / "context-memory" / "scripts" / "memory_tool.py"
        cls.memory_workflow = cls.repo_root / "skills" / "context-memory" / "scripts" / "memory_workflow.py"

    def test_memory_tool_help(self) -> None:
        proc = subprocess.run(
            ["python3", str(self.memory_tool), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Skill-local entrypoint", proc.stdout)

    def test_memory_workflow_help(self) -> None:
        proc = subprocess.run(
            ["python3", str(self.memory_workflow), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Deterministic memory workflow helper", proc.stdout)

    def test_memory_tool_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "note.md").write_text("# Note\n\nHello memory", encoding="utf-8")
            db_path = root / ".ai" / "memory" / "memory.db"

            reg = subprocess.run(
                [
                    "python3",
                    str(self.memory_tool),
                    "register_document",
                    "--repo-id",
                    "skill-test",
                    "--repo-root",
                    str(root),
                    "--db",
                    str(db_path),
                    "--locator",
                    "docs/note.md",
                    "--kind",
                    "doc",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(reg.returncode, 0, msg=reg.stderr)
            reg_out = json.loads(reg.stdout)
            self.assertTrue(reg_out["ok"])

            idx = subprocess.run(
                [
                    "python3",
                    str(self.memory_tool),
                    "index",
                    "--repo-id",
                    "skill-test",
                    "--repo-root",
                    str(root),
                    "--db",
                    str(db_path),
                    "--scope",
                    "delta",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(idx.returncode, 0, msg=idx.stderr)
            idx_out = json.loads(idx.stdout)
            self.assertTrue(idx_out["ok"])

            search = subprocess.run(
                [
                    "python3",
                    str(self.memory_tool),
                    "search",
                    "--repo-id",
                    "skill-test",
                    "--repo-root",
                    str(root),
                    "--db",
                    str(db_path),
                    "--query",
                    "note",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(search.returncode, 0, msg=search.stderr)
            search_out = json.loads(search.stdout)
            self.assertTrue(search_out["ok"])
            self.assertIn("results", search_out["result"])


if __name__ == "__main__":
    unittest.main()
