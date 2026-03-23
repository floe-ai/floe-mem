from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1


@dataclass
class DBConfig:
    path: Path


class MemoryDB:
    def __init__(self, config: DBConfig):
        self.config = config
        self.config.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.config.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self):
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def init(self) -> None:
        with self.tx() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS repositories (
                    id TEXT PRIMARY KEY,
                    root_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    active_version_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(repo_id, locator),
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS document_versions (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    commit_hash TEXT,
                    size_bytes INTEGER NOT NULL,
                    text_cache TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS anchors (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    symbol TEXT,
                    section TEXT,
                    line_start INTEGER,
                    line_end INTEGER,
                    path_hint TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (repo_id) REFERENCES repositories(id),
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_records (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    record_class TEXT NOT NULL,
                    durability_class TEXT NOT NULL,
                    latest_version_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS record_versions (
                    id TEXT PRIMARY KEY,
                    record_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (record_id) REFERENCES memory_records(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    from_type TEXT NOT NULL,
                    from_id TEXT NOT NULL,
                    to_type TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    weight REAL NOT NULL,
                    evidence_json TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(repo_id, from_type, from_id, to_type, to_id, edge_type),
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS lineage (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    parent_type TEXT NOT NULL,
                    parent_id TEXT NOT NULL,
                    child_type TEXT NOT NULL,
                    child_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(repo_id, parent_type, parent_id, child_type, child_id, relation),
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    heading TEXT,
                    text_content TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL,
                    source_digest TEXT,
                    derivation_method TEXT NOT NULL,
                    derivation_version TEXT NOT NULL,
                    freshness_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(repo_id, source_type, source_id, heading, source_digest),
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
                    repo_id,
                    source_type,
                    source_id,
                    heading,
                    text_content,
                    content=''
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dims INTEGER NOT NULL,
                    vector_blob BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS repo_map (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    inferred_kind TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT NOT NULL,
                    source_digest TEXT,
                    freshness_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(repo_id, locator),
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS code_affinity (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    file_path TEXT,
                    symbol TEXT,
                    test_hint TEXT,
                    weight REAL NOT NULL,
                    evidence_json TEXT NOT NULL,
                    freshness_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS provenance (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    source_digest TEXT,
                    commit_hash TEXT,
                    derivation_method TEXT NOT NULL,
                    derivation_version TEXT NOT NULL,
                    derived_at TEXT NOT NULL,
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS freshness (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reason TEXT,
                    checked_at TEXT NOT NULL,
                    UNIQUE(repo_id, target_type, target_id),
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bundle_headers (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    token_budget INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bundle_items (
                    id TEXT PRIMARY KEY,
                    bundle_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    inclusion_reason TEXT NOT NULL,
                    durability_class TEXT NOT NULL,
                    size_class TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (bundle_id) REFERENCES bundle_headers(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_events (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    target_type TEXT,
                    target_id TEXT,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (repo_id) REFERENCES repositories(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS index_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            cur.execute(
                "INSERT OR REPLACE INTO index_metadata(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )

    def fetchone(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(query, tuple(params)).fetchone()

    def fetchall(self, query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(query, tuple(params)).fetchall()

    def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        self.conn.execute(query, tuple(params))
        self.conn.commit()


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def from_json(raw: str | None) -> Any:
    if not raw:
        return None
    return json.loads(raw)
