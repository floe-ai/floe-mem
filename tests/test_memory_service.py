from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.memory_service import MemoryService, ServiceConfig


class MemoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / "src").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "guide.md").write_text(
            "# Guide\n\nThis document explains feature onboarding and acceptance criteria.",
            encoding="utf-8",
        )
        (self.root / "src" / "service.py").write_text(
            "def run_task():\n    return 'ok'\n",
            encoding="utf-8",
        )

        self.db = self.root / ".ai" / "memory" / "memory.db"
        self.svc = MemoryService(
            ServiceConfig(repo_id="repo-test", repo_root=self.root, db_path=self.db)
        )

    def tearDown(self) -> None:
        self.svc.close()
        self.tmp.cleanup()

    def test_retrieval_order_relationship_first(self) -> None:
        doc = self.svc.register_document("docs/guide.md", "doc")
        summary = self.svc.upsert_memory_record(
            record_class="summary",
            payload={"title": "Guide summary", "summary": "guide details", "status": "completed"},
            durability_class="durable_derived",
            provenance={"source_refs": [doc["document_id"]]},
        )
        task = self.svc.upsert_memory_record(
            record_class="ephemeral_run_note",
            payload={"note": "Investigate guide"},
            durability_class="ephemeral_run",
            provenance={"source_refs": [summary["record_id"]]},
        )

        self.svc.link_records(
            from_ref={"type": "memory_record", "id": task["record_id"]},
            to_ref={"type": "memory_record", "id": summary["record_id"]},
            edge_type="lineage_parent",
        )
        self.svc.index(scope="full", reason="test")

        result = self.svc.search(task["record_id"], limit=10)
        tiers = [r["tier"] for r in result["results"]]

        self.assertGreaterEqual(len(tiers), 2)
        self.assertEqual(tiers[0], "exact")
        self.assertIn("lineage", tiers)

    def test_invalidation_after_document_change(self) -> None:
        first = self.svc.register_document("docs/guide.md", "doc")
        self.svc.index(scope="delta", reason="initial")

        stale_before = self.svc.db.fetchone(
            "SELECT state FROM freshness WHERE target_type='document' AND target_id=?",
            (first["document_id"],),
        )
        self.assertEqual(stale_before["state"], "fresh")

        (self.root / "docs" / "guide.md").write_text(
            "# Guide\n\nChanged text with new constraints.",
            encoding="utf-8",
        )
        self.svc.register_document("docs/guide.md", "doc")

        stale_after_update = self.svc.db.fetchone(
            "SELECT state FROM freshness WHERE target_type='document' AND target_id=?",
            (first["document_id"],),
        )
        self.assertEqual(stale_after_update["state"], "stale")

        self.svc.index(scope="delta", reason="refresh")
        stale_after_reindex = self.svc.db.fetchone(
            "SELECT state FROM freshness WHERE target_type='document' AND target_id=?",
            (first["document_id"],),
        )
        self.assertEqual(stale_after_reindex["state"], "fresh")

    def test_bundle_is_bounded_and_auditable(self) -> None:
        doc = self.svc.register_document("docs/guide.md", "doc")
        self.svc.upsert_memory_record(
            record_class="summary",
            payload={"title": "Guide summary", "summary": "acceptance criteria guidance", "status": "completed"},
            durability_class="durable_derived",
            provenance={"source_refs": [doc["document_id"]]},
        )
        self.svc.index(scope="full", reason="bundle-test")

        bundle = self.svc.build_context_bundle(
            objective="guide acceptance criteria",
            profile="generic",
            token_budget=160,
        )

        self.assertLessEqual(bundle["token_used"], 160)
        self.assertTrue(bundle["items"])
        for item in bundle["items"]:
            self.assertIn("inclusion_reason", item)
            self.assertIn("tier", item)
            self.assertIn("durability_class", item)
            self.assertIn("token_estimate", item)


if __name__ == "__main__":
    unittest.main()
