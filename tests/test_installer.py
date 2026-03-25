from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]

    def test_non_interactive_copy_install_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            proc = subprocess.run(
                [
                    "uv",
                    "run",
                    "--directory",
                    str(self.repo_root),
                    "install-memory-skills",
                    "--target",
                    "codex",
                    "--scope",
                    "project",
                    "--project-root",
                    str(project_root),
                    "--yes",
                    "--non-interactive",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(len(payload["results"]), 1)
            self.assertEqual(payload["results"][0]["mode_used"], "copy")

            skill_dir = project_root / ".agents" / "skills" / "context-memory"
            self.assertTrue(skill_dir.exists())
            self.assertFalse(skill_dir.is_symlink())
            self.assertTrue((project_root / "tools" / "memory_service" / "runner.py").exists())

            help_proc = subprocess.run(
                [
                    "python3",
                    str(skill_dir / "scripts" / "memory_tool.py"),
                    "--help",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(help_proc.returncode, 0, msg=help_proc.stderr)
            self.assertTrue(
                (skill_dir / "scripts" / "memory.py").exists(),
                "simplified memory.py should be installed",
            )

    def test_script_path_entrypoint_help(self) -> None:
        proc = subprocess.run(
            [
                "uv",
                "run",
                str(self.repo_root / "tools" / "memory_service" / "install_skills.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("Install/sync context-memory skill", proc.stdout)

    def test_non_interactive_global_copy_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            proc = subprocess.run(
                [
                    "uv",
                    "run",
                    "--directory",
                    str(self.repo_root),
                    "install-memory-skills",
                    "--target",
                    "claude",
                    "--scope",
                    "global",
                    "--project-root",
                    str(project_root),
                    "--yes",
                    "--non-interactive",
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(project_root)},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            skill_dir = project_root / ".claude" / "skills" / "context-memory"
            self.assertTrue(skill_dir.exists())
            self.assertFalse(skill_dir.is_symlink())
            self.assertTrue((project_root / ".claude" / "tools" / "memory_service" / "runner.py").exists())

    def test_interactive_prompt_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            # 1=Codex, 1=project, y=confirm
            guided_input = "1\n1\ny\n"
            proc = subprocess.run(
                [
                    "uv",
                    "run",
                    "--directory",
                    str(self.repo_root),
                    "install-memory-skills",
                    "--project-root",
                    str(project_root),
                ],
                input=guided_input,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["results"][0]["client"], "codex")
            self.assertEqual(payload["results"][0]["mode_used"], "copy")


if __name__ == "__main__":
    unittest.main()
