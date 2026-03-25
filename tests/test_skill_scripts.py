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
        cls.memory_script = cls.repo_root / "skills" / "context-memory" / "scripts" / "memory.py"

    def test_memory_no_args(self) -> None:
        proc = subprocess.run(
            ["python3", str(self.memory_script)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        out = json.loads(proc.stdout)
        self.assertFalse(out["ok"])
        self.assertIn("no command provided", out["error"])

    def test_memory_save_and_recall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / ".ai" / "memory" / "memory.db"

            save = subprocess.run(
                [
                    "python3",
                    str(self.memory_script),
                    "--repo-id", "skill-test",
                    "--repo-root", str(root),
                    "--db", str(db_path),
                    "save",
                    "We chose JWT for authentication",
                    "--type", "decision",
                    "--tags", "auth",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(save.returncode, 0, msg=save.stderr)
            save_out = json.loads(save.stdout)
            self.assertTrue(save_out["ok"])
            self.assertIn("saved", save_out["result"])
            self.assertEqual(save_out["result"]["type"], "decision")

            recall = subprocess.run(
                [
                    "python3",
                    str(self.memory_script),
                    "--repo-id", "skill-test",
                    "--repo-root", str(root),
                    "--db", str(db_path),
                    "recall",
                    "authentication",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(recall.returncode, 0, msg=recall.stderr)
            recall_out = json.loads(recall.stdout)
            self.assertTrue(recall_out["ok"])
            self.assertIn("memories", recall_out["result"])

    def test_memory_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / ".ai" / "memory" / "memory.db"

            status = subprocess.run(
                [
                    "python3",
                    str(self.memory_script),
                    "--repo-id", "skill-test",
                    "--repo-root", str(root),
                    "--db", str(db_path),
                    "status",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(status.returncode, 0, msg=status.stderr)
            out = json.loads(status.stdout)
            self.assertTrue(out["ok"])
            self.assertIn("documents", out["result"])
            self.assertIn("memories", out["result"])


if __name__ == "__main__":
    unittest.main()
