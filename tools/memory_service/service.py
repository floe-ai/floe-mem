from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import DBConfig, MemoryDB, as_json, from_json

ALLOWED_RECORD_CLASSES = {
    "summary",
    "context_bundle",
    "repo_map_entry",
    "code_affinity_record",
    "provenance_record",
    "chunk_record",
    "ephemeral_run_note",
}

DURABILITY_CLASSES = {"canonical_reference", "durable_derived", "ephemeral_run"}
PROFILE_BUDGETS = {
    "generic": 1800,
    "implementer": 2200,
    "reviewer": 2200,
    "planner": 2600,
    "foreman": 2800,
}
TIER_ORDER = [
    "exact",
    "lineage",
    "explicit_links",
    "code_affinity",
    "validated_recent_history",
    "lexical_fts",
    "vector",
]
TIER_QUOTAS = {
    "exact": 6,
    "lineage": 6,
    "explicit_links": 6,
    "code_affinity": 5,
    "validated_recent_history": 4,
    "lexical_fts": 3,
    "vector": 2,
}
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class ServiceConfig:
    repo_id: str
    repo_root: Path
    db_path: Path
    enable_vector: bool = False


class MemoryService:
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.db = MemoryDB(DBConfig(path=config.db_path))
        self.db.init()
        self._ensure_repo()

    def close(self) -> None:
        self.db.close()

    def _ensure_repo(self) -> None:
        now = utc_now()
        with self.db.tx() as cur:
            cur.execute(
                """
                INSERT INTO repositories(id, root_path, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET root_path=excluded.root_path, updated_at=excluded.updated_at
                """,
                (self.config.repo_id, str(self.config.repo_root), now, now),
            )

    def register_document(
        self,
        locator: str,
        kind: str,
        metadata: dict[str, Any] | None = None,
        anchors: list[dict[str, Any]] | None = None,
        discovery_reason: str | None = None,
        confidence: float | None = None,
        commit_hash: str | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or {}
        anchors = anchors or []
        now = utc_now()

        doc_row = self.db.fetchone(
            "SELECT id FROM documents WHERE repo_id=? AND locator=?",
            (self.config.repo_id, locator),
        )
        document_id = doc_row["id"] if doc_row else new_id("doc")

        abs_path = (self.config.repo_root / locator).resolve()
        file_text = ""
        if abs_path.exists() and abs_path.is_file():
            file_text = abs_path.read_text(encoding="utf-8", errors="ignore")
        digest = digest_text(file_text)
        size_bytes = len(file_text.encode("utf-8"))
        version_id = new_id("dver")

        with self.db.tx() as cur:
            if doc_row:
                cur.execute(
                    """
                    UPDATE documents SET kind=?, metadata_json=?, updated_at=?
                    WHERE id=?
                    """,
                    (kind, as_json(metadata), now, document_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO documents(id, repo_id, locator, kind, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (document_id, self.config.repo_id, locator, kind, as_json(metadata), now, now),
                )

            cur.execute(
                """
                INSERT INTO document_versions(id, document_id, digest, commit_hash, size_bytes, text_cache, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (version_id, document_id, digest, commit_hash, size_bytes, "", now),
            )
            cur.execute(
                "UPDATE documents SET active_version_id=?, updated_at=? WHERE id=?",
                (version_id, now, document_id),
            )
            cur.execute("DELETE FROM anchors WHERE document_id=?", (document_id,))
            for anchor in anchors:
                anchor_id = new_id("anchor")
                cur.execute(
                    """
                    INSERT INTO anchors(
                        id, repo_id, document_id, symbol, section, line_start, line_end,
                        path_hint, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        anchor_id,
                        self.config.repo_id,
                        document_id,
                        anchor.get("symbol"),
                        anchor.get("section"),
                        anchor.get("line_start"),
                        anchor.get("line_end"),
                        anchor.get("path_hint"),
                        as_json(anchor.get("metadata") or {}),
                        now,
                        now,
                    ),
                )

            if discovery_reason is not None and confidence is not None:
                repo_map_id = new_id("rmap")
                cur.execute(
                    """
                    INSERT INTO repo_map(id, repo_id, locator, inferred_kind, confidence, reason,
                        source_digest, freshness_state, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(repo_id, locator) DO UPDATE SET
                        inferred_kind=excluded.inferred_kind,
                        confidence=excluded.confidence,
                        reason=excluded.reason,
                        source_digest=excluded.source_digest,
                        freshness_state='stale',
                        updated_at=excluded.updated_at
                    """,
                    (
                        repo_map_id,
                        self.config.repo_id,
                        locator,
                        kind,
                        float(confidence),
                        discovery_reason,
                        digest,
                        "fresh",
                        now,
                        now,
                    ),
                )

            self._set_freshness(cur, "document", document_id, "stale", "registered_or_updated")
            self._ingestion_event(
                cur,
                event_type="register_document",
                target_type="document",
                target_id=document_id,
                details={"locator": locator, "kind": kind, "digest": digest},
            )

        return {
            "document_id": document_id,
            "version_id": version_id,
            "freshness_state": "stale",
            "indexed_state": "pending_delta_index",
        }

    def upsert_memory_record(
        self,
        record_class: str,
        payload: dict[str, Any],
        durability_class: str,
        provenance: dict[str, Any],
        record_id: str | None = None,
    ) -> dict[str, Any]:
        if record_class not in ALLOWED_RECORD_CLASSES:
            raise ValueError(f"record_class '{record_class}' is not allowed")
        if durability_class not in DURABILITY_CLASSES:
            raise ValueError(f"durability_class '{durability_class}' is invalid")
        if record_class == "ephemeral_run_note" and durability_class != "ephemeral_run":
            raise ValueError("ephemeral_run_note cannot be persisted as durable without explicit promotion")
        if record_class == "chunk_record" and payload.get("authored_by"):
            raise ValueError("chunk_record is indexer-owned and cannot be agent-authored")
        if provenance.get("source_refs") is None:
            raise ValueError("provenance.source_refs is required")

        self._validate_record_payload(record_class, payload)

        now = utc_now()
        record_id = record_id or new_id("rec")
        version_id = new_id("rver")
        existing = self.db.fetchone("SELECT id FROM memory_records WHERE id=?", (record_id,))

        with self.db.tx() as cur:
            if existing:
                cur.execute(
                    """
                    UPDATE memory_records
                    SET record_class=?, durability_class=?, latest_version_id=?, updated_at=?
                    WHERE id=?
                    """,
                    (record_class, durability_class, version_id, now, record_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO memory_records(id, repo_id, record_class, durability_class, latest_version_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (record_id, self.config.repo_id, record_class, durability_class, version_id, now, now),
                )

            cur.execute(
                """
                INSERT INTO record_versions(id, record_id, payload_json, provenance_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (version_id, record_id, as_json(payload), as_json(provenance), now),
            )
            self._set_freshness(cur, "memory_record", record_id, "stale", "record_upsert")
            self._ingestion_event(
                cur,
                event_type="upsert_memory_record",
                target_type="memory_record",
                target_id=record_id,
                details={"record_class": record_class, "durability_class": durability_class},
            )

            if record_class == "code_affinity_record":
                self._upsert_code_affinity(cur, record_id, payload)
            if record_class == "provenance_record":
                self._insert_provenance_from_payload(cur, payload)

        return {
            "record_id": record_id,
            "record_version": version_id,
            "durability_class": durability_class,
            "validation_status": "ok",
        }

    def link_records(
        self,
        from_ref: dict[str, str],
        to_ref: dict[str, str],
        edge_type: str,
        weight: float = 1.0,
        evidence: dict[str, Any] | None = None,
        valid_from: str | None = None,
        valid_to: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        evidence = evidence or {}
        edge_row = self.db.fetchone(
            """
            SELECT id FROM edges
            WHERE repo_id=? AND from_type=? AND from_id=? AND to_type=? AND to_id=? AND edge_type=?
            """,
            (
                self.config.repo_id,
                from_ref["type"],
                from_ref["id"],
                to_ref["type"],
                to_ref["id"],
                edge_type,
            ),
        )
        edge_id = edge_row["id"] if edge_row else new_id("edge")
        with self.db.tx() as cur:
            if edge_row:
                cur.execute(
                    """
                    UPDATE edges
                    SET weight=?, evidence_json=?, valid_from=?, valid_to=?, updated_at=?
                    WHERE id=?
                    """,
                    (weight, as_json(evidence), valid_from, valid_to, now, edge_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO edges(
                        id, repo_id, from_type, from_id, to_type, to_id, edge_type,
                        weight, evidence_json, valid_from, valid_to, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge_id,
                        self.config.repo_id,
                        from_ref["type"],
                        from_ref["id"],
                        to_ref["type"],
                        to_ref["id"],
                        edge_type,
                        weight,
                        as_json(evidence),
                        valid_from,
                        valid_to,
                        now,
                        now,
                    ),
                )

            if edge_type.startswith("lineage"):
                lineage_id = new_id("lin")
                cur.execute(
                    """
                    INSERT INTO lineage(id, repo_id, parent_type, parent_id, child_type, child_id, relation, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(repo_id, parent_type, parent_id, child_type, child_id, relation)
                    DO UPDATE SET updated_at=excluded.updated_at
                    """,
                    (
                        lineage_id,
                        self.config.repo_id,
                        from_ref["type"],
                        from_ref["id"],
                        to_ref["type"],
                        to_ref["id"],
                        edge_type,
                        now,
                        now,
                    ),
                )
            self._set_freshness(cur, "edge", edge_id, "fresh", "explicit_link")
            self._ingestion_event(
                cur,
                event_type="link_records",
                target_type="edge",
                target_id=edge_id,
                details={"edge_type": edge_type, "from": from_ref, "to": to_ref},
            )

        return {"edge_id": edge_id, "status": "ok", "integrity": "validated"}

    def index(
        self,
        scope: str = "delta",
        targets: list[dict[str, str]] | None = None,
        reason: str | None = None,
        force_rebuild: bool = False,
    ) -> dict[str, Any]:
        if scope not in {"delta", "targeted", "full"}:
            raise ValueError("scope must be one of: delta, targeted, full")

        targets = targets or []
        indexed_counts = {"documents": 0, "records": 0, "chunks": 0, "repo_map": 0}
        invalidated_counts = {"chunks": 0, "freshness": 0}

        if scope in {"delta", "full"} and not targets:
            indexed_counts["repo_map"] += self._discover_candidates()

        docs = self._documents_to_index(scope=scope, targets=targets)
        records = self._records_to_index(scope=scope, targets=targets)

        with self.db.tx() as cur:
            if force_rebuild or scope == "full":
                cur.execute("DELETE FROM chunks WHERE repo_id=?", (self.config.repo_id,))
                cur.execute("DELETE FROM fts_chunks")
                invalidated_counts["chunks"] += cur.rowcount

            for doc in docs:
                indexed_counts["documents"] += 1
                invalidated_counts["chunks"] += self._invalidate_source_chunks(cur, "document", doc["id"])
                text = self._active_document_text(doc["id"]) or ""
                digest = self._active_document_digest(doc["id"])
                for heading, body in chunk_text(text):
                    chunk_id = new_id("chk")
                    token_est = estimate_tokens(body)
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO chunks(
                            id, repo_id, source_type, source_id, heading, text_content, token_estimate,
                            source_digest, derivation_method, derivation_version, freshness_state, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk_id,
                            self.config.repo_id,
                            "document",
                            doc["id"],
                            heading,
                            body,
                            token_est,
                            digest,
                            "chunk_markdown_or_plain",
                            "v1",
                            "fresh",
                            utc_now(),
                            utc_now(),
                        ),
                    )
                    if cur.rowcount:
                        indexed_counts["chunks"] += 1
                        cur.execute(
                            "INSERT INTO fts_chunks(rowid, repo_id, source_type, source_id, heading, text_content) VALUES (?, ?, ?, ?, ?, ?)",
                            (cur.lastrowid, self.config.repo_id, "document", doc["id"], heading or "", body),
                        )
                self._set_freshness(cur, "document", doc["id"], "fresh", reason or "indexed")

            for rec in records:
                indexed_counts["records"] += 1
                invalidated_counts["chunks"] += self._invalidate_source_chunks(cur, "memory_record", rec["id"])
                payload = self._latest_record_payload(rec["id"]) or {}
                text = extract_record_text(payload)
                if text:
                    chunk_id = new_id("chk")
                    token_est = estimate_tokens(text)
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO chunks(
                            id, repo_id, source_type, source_id, heading, text_content, token_estimate,
                            source_digest, derivation_method, derivation_version, freshness_state, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk_id,
                            self.config.repo_id,
                            "memory_record",
                            rec["id"],
                            rec["record_class"],
                            text,
                            token_est,
                            digest_text(text),
                            "chunk_record_payload",
                            "v1",
                            "fresh",
                            utc_now(),
                            utc_now(),
                        ),
                    )
                    if cur.rowcount:
                        indexed_counts["chunks"] += 1
                        cur.execute(
                            "INSERT INTO fts_chunks(rowid, repo_id, source_type, source_id, heading, text_content) VALUES (?, ?, ?, ?, ?, ?)",
                            (cur.lastrowid, self.config.repo_id, "memory_record", rec["id"], rec["record_class"], text),
                        )
                self._set_freshness(cur, "memory_record", rec["id"], "fresh", reason or "indexed")

            self._ingestion_event(
                cur,
                event_type="index",
                target_type="repository",
                target_id=self.config.repo_id,
                details={"scope": scope, "reason": reason, "force_rebuild": force_rebuild},
            )

        stale_remaining = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM freshness WHERE repo_id=? AND state='stale'",
            (self.config.repo_id,),
        )["c"]

        return {
            "indexed_counts": indexed_counts,
            "invalidated_counts": invalidated_counts,
            "stale_remaining": stale_remaining,
            "index_version": "v1",
        }

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        profile: str | None = None,
        limit: int = 20,
        override_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        filters = filters or {}
        override_policy = override_policy or {}
        normalized = query.strip()

        tiers: dict[str, list[dict[str, Any]]] = {tier: [] for tier in TIER_ORDER}

        exact_hits = self._exact_hits(normalized)
        tiers["exact"].extend(exact_hits)

        lineage_hits = self._lineage_hits(exact_hits)
        tiers["lineage"].extend(lineage_hits)

        link_hits = self._explicit_link_hits(exact_hits + lineage_hits)
        tiers["explicit_links"].extend(link_hits)

        affinity_hits = self._code_affinity_hits(normalized)
        tiers["code_affinity"].extend(affinity_hits)

        summary_hits = self._validated_summary_hits(normalized)
        tiers["validated_recent_history"].extend(summary_hits)

        lexical_hits = self._lexical_hits(normalized)
        tiers["lexical_fts"].extend(lexical_hits)

        if self.config.enable_vector:
            tiers["vector"].extend([])

        # Lower tiers cannot outrank higher tiers unless explicit override is set.
        allow_cross_tier_override = bool(override_policy.get("allow_cross_tier"))
        results: list[dict[str, Any]] = []
        seen = set()
        for tier in TIER_ORDER:
            tier_items = tiers[tier]
            tier_items.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            for item in tier_items:
                key = (item["source_type"], item["source_id"])
                if key in seen:
                    continue
                item["tier"] = tier
                if allow_cross_tier_override:
                    item["override_used"] = True
                results.append(item)
                seen.add(key)
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break

        return {"query": query, "results": results[:limit], "tiers": TIER_ORDER}

    def build_context_bundle(
        self,
        objective: str,
        focus_refs: list[dict[str, str]] | None = None,
        profile: str = "generic",
        token_budget: int | None = None,
    ) -> dict[str, Any]:
        focus_refs = focus_refs or []
        if profile not in PROFILE_BUDGETS:
            raise ValueError(f"unknown profile '{profile}'")
        budget = token_budget or PROFILE_BUDGETS[profile]

        seed_query = objective
        if focus_refs:
            seed_query += " " + " ".join(ref.get("id", "") for ref in focus_refs)
        search_res = self.search(query=seed_query, profile=profile, limit=40)
        if not search_res["results"]:
            fallback = self._bundle_fallback_candidates()
            if fallback:
                search_res["results"] = fallback

        bucket_counts = {tier: 0 for tier in TIER_ORDER}
        used_tokens = 0
        items: list[dict[str, Any]] = []

        for res in search_res["results"]:
            tier = res["tier"]
            if bucket_counts[tier] >= TIER_QUOTAS[tier]:
                continue
            est = int(res.get("token_estimate") or 120)
            if used_tokens + est > budget:
                continue
            payload = {
                "source_type": res["source_type"],
                "source_id": res["source_id"],
                "snippet": res.get("snippet"),
                "score": res.get("score"),
            }
            items.append(
                {
                    "source_type": res["source_type"],
                    "source_id": res["source_id"],
                    "tier": tier,
                    "inclusion_reason": res.get("why_selected", "ranked_result"),
                    "source_refs": res.get("source_refs", []),
                    "durability_class": res.get("durability_class", "durable_derived"),
                    "size_class": size_class(est),
                    "token_estimate": est,
                    "payload": payload,
                }
            )
            bucket_counts[tier] += 1
            used_tokens += est

        # Ensure bounded bundles still include at least one trustworthy item when results exist.
        if not items and search_res["results"]:
            top = search_res["results"][0]
            est = min(int(top.get("token_estimate") or 120), max(40, budget))
            items.append(
                {
                    "source_type": top["source_type"],
                    "source_id": top["source_id"],
                    "tier": top["tier"],
                    "inclusion_reason": top.get("why_selected", "ranked_result_forced_minimum"),
                    "source_refs": top.get("source_refs", []),
                    "durability_class": top.get("durability_class", "durable_derived"),
                    "size_class": size_class(est),
                    "token_estimate": est,
                    "payload": {
                        "source_type": top["source_type"],
                        "source_id": top["source_id"],
                        "snippet": top.get("snippet"),
                        "score": top.get("score"),
                    },
                }
            )
            used_tokens = est

        bundle_id = new_id("bundle")
        now = utc_now()
        with self.db.tx() as cur:
            cur.execute(
                """
                INSERT INTO bundle_headers(id, repo_id, profile, objective, token_budget, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (bundle_id, self.config.repo_id, profile, objective, budget, "ready", now),
            )
            for it in items:
                cur.execute(
                    """
                    INSERT INTO bundle_items(
                        id, bundle_id, source_type, source_id, tier, inclusion_reason,
                        durability_class, size_class, token_estimate, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("bit"),
                        bundle_id,
                        it["source_type"],
                        it["source_id"],
                        it["tier"],
                        it["inclusion_reason"],
                        it["durability_class"],
                        it["size_class"],
                        it["token_estimate"],
                        as_json(it["payload"]),
                        now,
                    ),
                )

        stop_state = {
            "objective_clear": bool(items),
            "constraints_known": any("constraint" in (i["inclusion_reason"] or "") for i in items),
            "likely_files_or_symbols_identified": any(i["tier"] in {"exact", "code_affinity", "explicit_links"} for i in items),
            "verification_path_present": any(i["tier"] == "validated_recent_history" for i in items),
            "acceptance_criteria_clear": any(i["tier"] in {"lineage", "explicit_links"} for i in items),
        }

        return {
            "bundle_id": bundle_id,
            "profile": profile,
            "token_budget": budget,
            "token_used": used_tokens,
            "items": items,
            "stop_state": stop_state,
        }

    # -----------------
    # Internal helpers
    # -----------------

    def _validate_record_payload(self, record_class: str, payload: dict[str, Any]) -> None:
        required = {
            "summary": ["title", "summary", "status"],
            "context_bundle": ["objective", "items"],
            "repo_map_entry": ["locator", "inferred_kind", "confidence"],
            "code_affinity_record": ["subject", "affinities"],
            "provenance_record": ["target", "source_ref", "derivation_method"],
            "chunk_record": ["source", "text"],
            "ephemeral_run_note": ["note"],
        }
        for key in required[record_class]:
            if key not in payload:
                raise ValueError(f"payload missing required key '{key}' for class '{record_class}'")

    def _set_freshness(self, cur, target_type: str, target_id: str, state: str, reason: str) -> None:
        now = utc_now()
        cur.execute(
            """
            INSERT INTO freshness(id, repo_id, target_type, target_id, state, reason, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo_id, target_type, target_id) DO UPDATE SET
                state=excluded.state,
                reason=excluded.reason,
                checked_at=excluded.checked_at
            """,
            (new_id("fresh"), self.config.repo_id, target_type, target_id, state, reason, now),
        )

    def _ingestion_event(self, cur, event_type: str, target_type: str, target_id: str, details: dict[str, Any]) -> None:
        cur.execute(
            """
            INSERT INTO ingestion_events(id, repo_id, event_type, target_type, target_id, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id("evt"), self.config.repo_id, event_type, target_type, target_id, as_json(details), utc_now()),
        )

    def _insert_provenance_from_payload(self, cur, payload: dict[str, Any]) -> None:
        target = payload["target"]
        cur.execute(
            """
            INSERT INTO provenance(
                id, repo_id, target_type, target_id, source_ref, source_digest,
                commit_hash, derivation_method, derivation_version, derived_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("prov"),
                self.config.repo_id,
                target["type"],
                target["id"],
                payload["source_ref"],
                payload.get("source_digest"),
                payload.get("commit_hash"),
                payload["derivation_method"],
                payload.get("derivation_version", "v1"),
                utc_now(),
            ),
        )

    def _upsert_code_affinity(self, cur, record_id: str, payload: dict[str, Any]) -> None:
        subject = payload["subject"]
        for affinity in payload.get("affinities", []):
            cur.execute(
                """
                INSERT INTO code_affinity(
                    id, repo_id, subject_type, subject_id, file_path, symbol, test_hint,
                    weight, evidence_json, freshness_state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("caff"),
                    self.config.repo_id,
                    subject.get("type", "record"),
                    subject.get("id", record_id),
                    affinity.get("file_path"),
                    affinity.get("symbol"),
                    affinity.get("test_hint"),
                    float(affinity.get("weight", 1.0)),
                    as_json(affinity.get("evidence") or {}),
                    "fresh",
                    utc_now(),
                    utc_now(),
                ),
            )

    def _discover_candidates(self) -> int:
        count = 0
        root = self.config.repo_root
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(root))
            if rel.startswith(".git/") or "/.git/" in rel:
                continue
            if rel.startswith("node_modules/") or "/node_modules/" in rel:
                continue
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".zip", ".pdf", ".bin"}:
                continue
            if path.stat().st_size > 300_000:
                continue
            kind = infer_kind(rel)
            conf = 0.7 if kind != "code" else 0.5
            self.register_document(
                locator=rel,
                kind=kind,
                metadata={"discovered": True},
                anchors=[],
                discovery_reason="shallow_deterministic_scan",
                confidence=conf,
            )
            count += 1
            if count >= 200:
                break
        return count

    def _documents_to_index(self, scope: str, targets: list[dict[str, str]]) -> list[dict[str, Any]]:
        if scope == "targeted" and targets:
            doc_ids = [t["id"] for t in targets if t.get("type") == "document"]
            if not doc_ids:
                return []
            q = "SELECT id FROM documents WHERE repo_id=? AND id IN ({})".format(
                ",".join("?" for _ in doc_ids)
            )
            rows = self.db.fetchall(q, (self.config.repo_id, *doc_ids))
            return [dict(r) for r in rows]

        if scope == "delta":
            rows = self.db.fetchall(
                """
                SELECT d.id
                FROM documents d
                LEFT JOIN freshness f
                  ON f.repo_id=d.repo_id AND f.target_type='document' AND f.target_id=d.id
                WHERE d.repo_id=? AND (f.state IS NULL OR f.state='stale')
                """,
                (self.config.repo_id,),
            )
            return [dict(r) for r in rows]

        rows = self.db.fetchall("SELECT id FROM documents WHERE repo_id=?", (self.config.repo_id,))
        return [dict(r) for r in rows]

    def _records_to_index(self, scope: str, targets: list[dict[str, str]]) -> list[dict[str, Any]]:
        if scope == "targeted" and targets:
            rec_ids = [t["id"] for t in targets if t.get("type") == "memory_record"]
            if not rec_ids:
                return []
            q = "SELECT id, record_class FROM memory_records WHERE repo_id=? AND id IN ({})".format(
                ",".join("?" for _ in rec_ids)
            )
            rows = self.db.fetchall(q, (self.config.repo_id, *rec_ids))
            return [dict(r) for r in rows]

        if scope == "delta":
            rows = self.db.fetchall(
                """
                SELECT r.id, r.record_class
                FROM memory_records r
                LEFT JOIN freshness f
                  ON f.repo_id=r.repo_id AND f.target_type='memory_record' AND f.target_id=r.id
                WHERE r.repo_id=? AND (f.state IS NULL OR f.state='stale')
                """,
                (self.config.repo_id,),
            )
            return [dict(r) for r in rows]

        rows = self.db.fetchall(
            "SELECT id, record_class FROM memory_records WHERE repo_id=?", (self.config.repo_id,)
        )
        return [dict(r) for r in rows]

    def _active_document_text(self, document_id: str) -> str:
        row = self.db.fetchone(
            "SELECT locator FROM documents WHERE id=?",
            (document_id,),
        )
        if not row:
            return ""
        abs_path = (self.config.repo_root / row["locator"]).resolve()
        if abs_path.exists() and abs_path.is_file():
            return abs_path.read_text(encoding="utf-8", errors="ignore")
        return ""

    def _active_document_digest(self, document_id: str) -> str:
        row = self.db.fetchone(
            """
            SELECT dv.digest AS digest
            FROM documents d
            JOIN document_versions dv ON dv.id=d.active_version_id
            WHERE d.id=?
            """,
            (document_id,),
        )
        return row["digest"] if row else ""

    def _latest_record_payload(self, record_id: str) -> dict[str, Any]:
        row = self.db.fetchone(
            """
            SELECT rv.payload_json
            FROM memory_records r
            JOIN record_versions rv ON rv.id=r.latest_version_id
            WHERE r.id=?
            """,
            (record_id,),
        )
        return from_json(row["payload_json"]) if row else {}

    def _invalidate_source_chunks(self, cur, source_type: str, source_id: str) -> int:
        cur.execute(
            "DELETE FROM chunks WHERE repo_id=? AND source_type=? AND source_id=?",
            (self.config.repo_id, source_type, source_id),
        )
        deleted = cur.rowcount
        cur.execute(
            "DELETE FROM fts_chunks WHERE repo_id=? AND source_type=? AND source_id=?",
            (self.config.repo_id, source_type, source_id),
        )
        return deleted

    def _exact_hits(self, normalized_query: str) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []

        doc_rows = self.db.fetchall(
            """
            SELECT id, locator, kind, metadata_json
            FROM documents
            WHERE repo_id=? AND (id=? OR locator=? OR locator LIKE ?)
            """,
            (self.config.repo_id, normalized_query, normalized_query, f"%{normalized_query}%"),
        )
        for row in doc_rows:
            hits.append(
                {
                    "source_type": "document",
                    "source_id": row["id"],
                    "score": 100.0,
                    "why_selected": "exact_id_or_path_match",
                    "durability_class": "canonical_reference",
                    "snippet": row["locator"],
                    "source_refs": [row["id"]],
                    "token_estimate": 40,
                }
            )

        anchor_rows = self.db.fetchall(
            """
            SELECT id, document_id, symbol, section, path_hint
            FROM anchors
            WHERE repo_id=? AND (symbol=? OR section=? OR path_hint=?)
            """,
            (self.config.repo_id, normalized_query, normalized_query, normalized_query),
        )
        for row in anchor_rows:
            hits.append(
                {
                    "source_type": "anchor",
                    "source_id": row["id"],
                    "score": 99.0,
                    "why_selected": "exact_symbol_or_section_match",
                    "durability_class": "canonical_reference",
                    "snippet": row["symbol"] or row["section"] or row["path_hint"],
                    "source_refs": [row["document_id"]],
                    "token_estimate": 50,
                }
            )

        rec_rows = self.db.fetchall(
            """
            SELECT id, record_class, durability_class
            FROM memory_records
            WHERE repo_id=? AND id=?
            """,
            (self.config.repo_id, normalized_query),
        )
        for row in rec_rows:
            hits.append(
                {
                    "source_type": "memory_record",
                    "source_id": row["id"],
                    "score": 95.0,
                    "why_selected": "exact_record_id_match",
                    "durability_class": row["durability_class"],
                    "snippet": row["record_class"],
                    "source_refs": [row["id"]],
                    "token_estimate": 60,
                }
            )

        return hits

    def _lineage_hits(self, seed_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seeds = {(h["source_type"], h["source_id"]) for h in seed_hits}
        if not seeds:
            return []
        hits: list[dict[str, Any]] = []
        for s_type, s_id in seeds:
            rows = self.db.fetchall(
                """
                SELECT parent_type, parent_id, child_type, child_id, relation
                FROM lineage
                WHERE repo_id=? AND ((parent_type=? AND parent_id=?) OR (child_type=? AND child_id=?))
                """,
                (self.config.repo_id, s_type, s_id, s_type, s_id),
            )
            for row in rows:
                if row["parent_type"] == s_type and row["parent_id"] == s_id:
                    source_type, source_id = row["child_type"], row["child_id"]
                else:
                    source_type, source_id = row["parent_type"], row["parent_id"]
                hits.append(
                    {
                        "source_type": source_type,
                        "source_id": source_id,
                        "score": 85.0,
                        "why_selected": f"lineage:{row['relation']}",
                        "durability_class": "durable_derived",
                        "source_refs": [s_id],
                        "token_estimate": 90,
                    }
                )
        return hits

    def _explicit_link_hits(self, seed_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seeds = {(h["source_type"], h["source_id"]) for h in seed_hits}
        if not seeds:
            return []
        hits: list[dict[str, Any]] = []
        for s_type, s_id in seeds:
            rows = self.db.fetchall(
                """
                SELECT from_type, from_id, to_type, to_id, edge_type, weight
                FROM edges
                WHERE repo_id=? AND ((from_type=? AND from_id=?) OR (to_type=? AND to_id=?))
                """,
                (self.config.repo_id, s_type, s_id, s_type, s_id),
            )
            for row in rows:
                if row["from_type"] == s_type and row["from_id"] == s_id:
                    source_type, source_id = row["to_type"], row["to_id"]
                else:
                    source_type, source_id = row["from_type"], row["from_id"]
                hits.append(
                    {
                        "source_type": source_type,
                        "source_id": source_id,
                        "score": 75.0 + float(row["weight"]),
                        "why_selected": f"explicit_link:{row['edge_type']}",
                        "durability_class": "durable_derived",
                        "source_refs": [s_id],
                        "token_estimate": 110,
                    }
                )
        return hits

    def _code_affinity_hits(self, normalized_query: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """
            SELECT id, subject_type, subject_id, file_path, symbol, test_hint, weight
            FROM code_affinity
            WHERE repo_id=? AND (
                file_path LIKE ? OR symbol LIKE ? OR test_hint LIKE ? OR subject_id=?
            )
            ORDER BY weight DESC, updated_at DESC
            LIMIT 20
            """,
            (
                self.config.repo_id,
                f"%{normalized_query}%",
                f"%{normalized_query}%",
                f"%{normalized_query}%",
                normalized_query,
            ),
        )
        hits = []
        for row in rows:
            hits.append(
                {
                    "source_type": row["subject_type"],
                    "source_id": row["subject_id"],
                    "score": 65.0 + float(row["weight"]),
                    "why_selected": "code_affinity_match",
                    "durability_class": "durable_derived",
                    "snippet": row["file_path"] or row["symbol"] or row["test_hint"],
                    "source_refs": [row["id"]],
                    "token_estimate": 120,
                }
            )
        return hits

    def _validated_summary_hits(self, normalized_query: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """
            SELECT r.id, r.durability_class, rv.payload_json, r.updated_at
            FROM memory_records r
            JOIN record_versions rv ON rv.id=r.latest_version_id
            WHERE r.repo_id=? AND r.record_class='summary'
            ORDER BY r.updated_at DESC
            LIMIT 40
            """,
            (self.config.repo_id,),
        )
        hits = []
        for row in rows:
            payload = from_json(row["payload_json"]) or {}
            text = json.dumps(payload, ensure_ascii=False).lower()
            status = str(payload.get("status", "")).lower()
            if normalized_query.lower() not in text:
                continue
            if status not in {"completed", "validated", "accepted", "blocked", "partial"}:
                continue
            hits.append(
                {
                    "source_type": "memory_record",
                    "source_id": row["id"],
                    "score": 55.0,
                    "why_selected": "recent_validated_summary",
                    "durability_class": row["durability_class"],
                    "snippet": payload.get("summary") or payload.get("title"),
                    "source_refs": [row["id"]],
                    "token_estimate": estimate_tokens(payload.get("summary") or ""),
                }
            )
        return hits

    def _lexical_hits(self, normalized_query: str) -> list[dict[str, Any]]:
        if not normalized_query:
            return []
        rows = self.db.fetchall(
            """
            SELECT source_type, source_id, heading, text_content
            FROM fts_chunks
            WHERE repo_id=? AND fts_chunks MATCH ?
            LIMIT 20
            """,
            (self.config.repo_id, normalized_query),
        )
        hits = []
        for row in rows:
            snippet = (row["text_content"] or "")[:220]
            hits.append(
                {
                    "source_type": row["source_type"],
                    "source_id": row["source_id"],
                    "score": 45.0,
                    "why_selected": "lexical_fts_match",
                    "durability_class": "durable_derived",
                    "snippet": snippet,
                    "source_refs": [row["source_id"]],
                    "token_estimate": estimate_tokens(snippet),
                }
            )
        return hits

    def _bundle_fallback_candidates(self) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """
            SELECT r.id, r.durability_class, rv.payload_json
            FROM memory_records r
            JOIN record_versions rv ON rv.id=r.latest_version_id
            WHERE r.repo_id=? AND r.record_class='summary'
            ORDER BY r.updated_at DESC
            LIMIT 1
            """,
            (self.config.repo_id,),
        )
        if rows:
            payload = from_json(rows[0]["payload_json"]) or {}
            snippet = payload.get("summary") or payload.get("title") or "recent summary"
            return [
                {
                    "source_type": "memory_record",
                    "source_id": rows[0]["id"],
                    "tier": "validated_recent_history",
                    "score": 54.0,
                    "why_selected": "bundle_fallback_recent_summary",
                    "durability_class": rows[0]["durability_class"],
                    "snippet": snippet,
                    "source_refs": [rows[0]["id"]],
                    "token_estimate": estimate_tokens(snippet),
                }
            ]

        docs = self.db.fetchall(
            """
            SELECT id, locator
            FROM documents
            WHERE repo_id=?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (self.config.repo_id,),
        )
        if docs:
            return [
                {
                    "source_type": "document",
                    "source_id": docs[0]["id"],
                    "tier": "exact",
                    "score": 52.0,
                    "why_selected": "bundle_fallback_recent_document",
                    "durability_class": "canonical_reference",
                    "snippet": docs[0]["locator"],
                    "source_refs": [docs[0]["id"]],
                    "token_estimate": 60,
                }
            ]

        return []


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def infer_kind(rel_path: str) -> str:
    low = rel_path.lower()
    if low.endswith(".py") or low.endswith(".ts") or low.endswith(".tsx") or low.endswith(".js"):
        return "code"
    if "adr" in low:
        return "adr"
    if "prd" in low:
        return "prd"
    if "task" in low:
        return "task"
    if "feature" in low:
        return "feature"
    if "epic" in low:
        return "epic"
    return "doc"


def extract_record_text(payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    important = []
    for key in ["title", "summary", "intent", "objective", "note", "details"]:
        if key in payload:
            important.append(str(payload[key]))
    important.append(json.dumps(payload, ensure_ascii=False))
    return "\n".join(important)[:12000]


def chunk_text(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines() or [""]
    chunks: list[tuple[str, list[str]]] = [("ROOT", [])]
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            chunks.append((m.group(2).strip(), [line]))
        else:
            chunks[-1][1].append(line)
    out = []
    for heading, body_lines in chunks:
        body = "\n".join(body_lines).strip()
        if body:
            out.append((heading, body[:12000]))
    return out


def estimate_tokens(text: str) -> int:
    if not text:
        return 1
    return max(1, int(len(text.split()) / 0.75))


def size_class(tokens: int) -> str:
    if tokens <= 120:
        return "xs"
    if tokens <= 260:
        return "sm"
    if tokens <= 500:
        return "md"
    return "lg"
