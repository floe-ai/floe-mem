from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .service import MemoryService, ServiceConfig

# --- Simplified type → record mapping ---
SIMPLE_TYPES = {"decision", "pattern", "issue", "learning", "preference", "constraint"}


def load_json_arg(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    if value.startswith("@"):
        p = Path(value[1:])
        return json.loads(p.read_text(encoding="utf-8"))
    return json.loads(value)


def _make_svc(args: argparse.Namespace) -> MemoryService:
    return MemoryService(
        ServiceConfig(
            repo_id=args.repo_id,
            repo_root=Path(args.repo_root).resolve(),
            db_path=Path(args.db).resolve(),
            enable_vector=bool(args.enable_vector),
        )
    )


def _auto_title(content: str, max_len: int = 80) -> str:
    """Derive a short title from content."""
    line = content.strip().split("\n", 1)[0]
    if len(line) <= max_len:
        return line
    return line[:max_len - 3] + "..."


# ─── Simplified commands ────────────────────────────────────────────

def _cmd_save(args: argparse.Namespace) -> dict[str, Any]:
    """Save a memory with flat arguments. Builds payload/provenance automatically."""
    svc = _make_svc(args)
    try:
        content = args.content
        mem_type = args.type or "learning"
        title = args.title or _auto_title(content)
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

        payload = {
            "title": title,
            "summary": content,
            "status": "accepted",
            "type": mem_type,
        }
        if tags:
            payload["tags"] = tags

        provenance = {
            "source_refs": [],
            "agent": args.agent or "unknown",
            "task": args.task or "",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        result = svc.upsert_memory_record(
            record_class="summary",
            payload=payload,
            durability_class="durable_derived",
            provenance=provenance,
            record_id=args.record_id,
        )
        return {"saved": result["record_id"], "type": mem_type, "title": title}
    finally:
        svc.close()


def _cmd_recall(args: argparse.Namespace) -> dict[str, Any]:
    """Search memory and return clean results."""
    svc = _make_svc(args)
    try:
        raw = svc.search(query=args.query, limit=args.limit or 5)
        memories = []
        for r in raw.get("results", []):
            entry: dict[str, Any] = {
                "id": r["source_id"],
                "type": r["source_type"],
                "tier": r["tier"],
            }
            snippet = r.get("snippet", "")
            if snippet:
                entry["snippet"] = snippet[:500]
            score = r.get("score")
            if score is not None:
                entry["score"] = score
            memories.append(entry)
        return {"query": args.query, "count": len(memories), "memories": memories}
    finally:
        svc.close()


def _cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    """Overview of what's in memory."""
    svc = _make_svc(args)
    try:
        db = svc.db
        doc_count = db.fetchone("SELECT COUNT(*) FROM documents WHERE repo_id=?", (svc.config.repo_id,))[0]
        rec_count = db.fetchone("SELECT COUNT(*) FROM memory_records WHERE repo_id=?", (svc.config.repo_id,))[0]
        chunk_count = db.fetchone(
            "SELECT COUNT(*) FROM chunks WHERE repo_id=?",
            (svc.config.repo_id,),
        )[0]

        recent_records = db.fetchall(
            """SELECT mr.id, mr.record_class, mr.durability_class, mr.updated_at,
                      rv.payload_json
               FROM memory_records mr
               JOIN record_versions rv ON rv.id = mr.latest_version_id
               WHERE mr.repo_id=?
               ORDER BY mr.updated_at DESC LIMIT 10""",
            (svc.config.repo_id,),
        )
        recent = []
        for row in recent_records:
            payload = json.loads(row[4]) if row[4] else {}
            recent.append({
                "id": row[0],
                "class": row[1],
                "title": payload.get("title", payload.get("note", "")),
                "type": payload.get("type", ""),
                "updated": row[3],
            })

        return {
            "documents": doc_count,
            "memories": rec_count,
            "chunks": chunk_count,
            "recent": recent,
        }
    finally:
        svc.close()


def _cmd_remember(args: argparse.Namespace) -> dict[str, Any]:
    """Register file(s) and index in one step."""
    svc = _make_svc(args)
    try:
        registered = []
        for filepath in args.files:
            result = svc.register_document(locator=filepath, kind=args.kind or "doc")
            registered.append({"file": filepath, "doc_id": result["document_id"]})

        idx = svc.index(scope="delta", reason="remember_command")
        return {
            "registered": registered,
            "indexed": idx.get("indexed_counts", {}),
        }
    finally:
        svc.close()


def _cmd_context(args: argparse.Namespace) -> dict[str, Any]:
    """Build a context bundle for an objective."""
    svc = _make_svc(args)
    try:
        result = svc.build_context_bundle(
            objective=args.objective,
            profile=args.profile or "implementer",
            token_budget=args.token_budget,
        )
        return result
    finally:
        svc.close()


# ─── Parser ─────────────────────────────────────────────────────────

def _add_global_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--repo-id", default="default")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--db", default=".ai/memory/memory.db")
    ap.add_argument("--enable-vector", action="store_true")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="memory", description="Repo-local memory service CLI")
    _add_global_args(ap)

    sub = ap.add_subparsers(dest="cmd", required=True)

    # ── Simplified commands ──

    p_save = sub.add_parser("save", help="Save a memory (decision, pattern, learning, etc.)")
    p_save.add_argument("content", help="The memory content to save")
    p_save.add_argument("--type", choices=sorted(SIMPLE_TYPES), default="learning",
                        help="Memory type (default: learning)")
    p_save.add_argument("--tags", help="Comma-separated tags")
    p_save.add_argument("--title", help="Short title (auto-derived if omitted)")
    p_save.add_argument("--agent", help="Agent identifier")
    p_save.add_argument("--task", help="Current task description")
    p_save.add_argument("--record-id", help="Update existing record by ID")

    p_recall = sub.add_parser("recall", help="Search memory for relevant context")
    p_recall.add_argument("query", help="What to search for")
    p_recall.add_argument("--limit", type=int, default=5, help="Max results (default: 5)")

    p_status = sub.add_parser("status", help="Show memory overview")

    p_remember = sub.add_parser("remember", help="Register and index file(s)")
    p_remember.add_argument("files", nargs="+", help="File path(s) to register")
    p_remember.add_argument("--kind", default="doc", help="Document kind (default: doc)")

    p_context = sub.add_parser("context", help="Build context bundle for an objective")
    p_context.add_argument("objective", help="What you are trying to accomplish")
    p_context.add_argument("--profile", default="implementer",
                           choices=["generic", "implementer", "reviewer", "planner", "foreman"])
    p_context.add_argument("--token-budget", type=int, help="Override token budget")

    # ── Full API commands ──

    p_reg = sub.add_parser("register_document")
    p_reg.add_argument("--locator", required=True)
    p_reg.add_argument("--kind", required=True)
    p_reg.add_argument("--metadata")
    p_reg.add_argument("--anchors")
    p_reg.add_argument("--discovery-reason")
    p_reg.add_argument("--confidence", type=float)
    p_reg.add_argument("--commit-hash")

    p_up = sub.add_parser("upsert_memory_record")
    p_up.add_argument("--record-class", required=True)
    p_up.add_argument("--payload", required=True)
    p_up.add_argument("--durability-class", required=True)
    p_up.add_argument("--provenance", required=True)
    p_up.add_argument("--record-id")

    p_link = sub.add_parser("link_records")
    p_link.add_argument("--from-ref", required=True)
    p_link.add_argument("--to-ref", required=True)
    p_link.add_argument("--edge-type", required=True)
    p_link.add_argument("--weight", type=float, default=1.0)
    p_link.add_argument("--evidence")
    p_link.add_argument("--valid-from")
    p_link.add_argument("--valid-to")

    p_idx = sub.add_parser("index")
    p_idx.add_argument("--scope", default="delta", choices=["delta", "targeted", "full"])
    p_idx.add_argument("--targets")
    p_idx.add_argument("--reason")
    p_idx.add_argument("--force-rebuild", action="store_true")

    p_search = sub.add_parser("search")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--filters")
    p_search.add_argument("--profile")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--override-policy")

    p_bundle = sub.add_parser("build_context_bundle")
    p_bundle.add_argument("--objective", required=True)
    p_bundle.add_argument("--focus-refs")
    p_bundle.add_argument("--profile", default="generic")
    p_bundle.add_argument("--token-budget", type=int)

    return ap


SIMPLE_COMMANDS = {"save", "recall", "status", "remember", "context"}


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)

    try:
        # Simplified commands handle their own service lifecycle
        if args.cmd in SIMPLE_COMMANDS:
            handler = {
                "save": _cmd_save,
                "recall": _cmd_recall,
                "status": _cmd_status,
                "remember": _cmd_remember,
                "context": _cmd_context,
            }[args.cmd]
            out = handler(args)
            print(json.dumps({"ok": True, "result": out}, ensure_ascii=False, indent=2))
            return 0

        # Full API commands
        svc = _make_svc(args)
        try:
            if args.cmd == "register_document":
                out = svc.register_document(
                    locator=args.locator,
                    kind=args.kind,
                    metadata=load_json_arg(args.metadata, {}),
                    anchors=load_json_arg(args.anchors, []),
                    discovery_reason=args.discovery_reason,
                    confidence=args.confidence,
                    commit_hash=args.commit_hash,
                )
            elif args.cmd == "upsert_memory_record":
                out = svc.upsert_memory_record(
                    record_class=args.record_class,
                    payload=load_json_arg(args.payload, {}),
                    durability_class=args.durability_class,
                    provenance=load_json_arg(args.provenance, {}),
                    record_id=args.record_id,
                )
            elif args.cmd == "link_records":
                out = svc.link_records(
                    from_ref=load_json_arg(args.from_ref, {}),
                    to_ref=load_json_arg(args.to_ref, {}),
                    edge_type=args.edge_type,
                    weight=args.weight,
                    evidence=load_json_arg(args.evidence, {}),
                    valid_from=args.valid_from,
                    valid_to=args.valid_to,
                )
            elif args.cmd == "index":
                out = svc.index(
                    scope=args.scope,
                    targets=load_json_arg(args.targets, []),
                    reason=args.reason,
                    force_rebuild=bool(args.force_rebuild),
                )
            elif args.cmd == "search":
                out = svc.search(
                    query=args.query,
                    filters=load_json_arg(args.filters, {}),
                    profile=args.profile,
                    limit=args.limit,
                    override_policy=load_json_arg(args.override_policy, {}),
                )
            elif args.cmd == "build_context_bundle":
                out = svc.build_context_bundle(
                    objective=args.objective,
                    focus_refs=load_json_arg(args.focus_refs, []),
                    profile=args.profile,
                    token_budget=args.token_budget,
                )
            else:
                raise ValueError(f"unknown command {args.cmd}")

            print(json.dumps({"ok": True, "result": out}, ensure_ascii=False, indent=2))
            return 0
        finally:
            svc.close()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "command": args.cmd}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
