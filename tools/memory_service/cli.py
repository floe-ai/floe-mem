from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .service import MemoryService, ServiceConfig

MEMORY_TYPES = {"decision", "pattern", "issue", "learning", "preference", "constraint"}


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
    line = content.strip().split("\n", 1)[0]
    if len(line) <= max_len:
        return line
    return line[:max_len - 3] + "..."


def _cmd_save(args: argparse.Namespace) -> dict[str, Any]:
    svc = _make_svc(args)
    try:
        title = args.title or _auto_title(args.content)
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
        payload = {
            "title": title,
            "summary": args.content,
            "status": "accepted",
            "type": args.type or "learning",
        }
        if tags:
            payload["tags"] = tags

        result = svc.upsert_memory_record(
            record_class="summary",
            payload=payload,
            durability_class="durable_derived",
            provenance={
                "source_refs": [],
                "agent": args.agent or "unknown",
                "task": args.task or "",
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
            record_id=args.record_id,
        )
        return {"saved": result["record_id"], "type": payload["type"], "title": title}
    finally:
        svc.close()


def _cmd_recall(args: argparse.Namespace) -> dict[str, Any]:
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
    svc = _make_svc(args)
    try:
        db = svc.db
        repo_id = svc.config.repo_id
        doc_count = db.fetchone("SELECT COUNT(*) FROM documents WHERE repo_id=?", (repo_id,))[0]
        rec_count = db.fetchone("SELECT COUNT(*) FROM memory_records WHERE repo_id=?", (repo_id,))[0]
        chunk_count = db.fetchone("SELECT COUNT(*) FROM chunks WHERE repo_id=?", (repo_id,))[0]

        recent_records = db.fetchall(
            """SELECT mr.id, mr.record_class, rv.payload_json, mr.updated_at
               FROM memory_records mr
               JOIN record_versions rv ON rv.id = mr.latest_version_id
               WHERE mr.repo_id=?
               ORDER BY mr.updated_at DESC LIMIT 10""",
            (repo_id,),
        )
        recent = []
        for row in recent_records:
            payload = json.loads(row[2]) if row[2] else {}
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
    svc = _make_svc(args)
    try:
        registered = []
        for filepath in args.files:
            result = svc.register_document(locator=filepath, kind=args.kind or "doc")
            registered.append({"file": filepath, "doc_id": result["document_id"]})
        idx = svc.index(scope="delta", reason="remember_command")
        return {"registered": registered, "indexed": idx.get("indexed_counts", {})}
    finally:
        svc.close()


def _cmd_context(args: argparse.Namespace) -> dict[str, Any]:
    svc = _make_svc(args)
    try:
        return svc.build_context_bundle(
            objective=args.objective,
            profile=args.profile or "implementer",
            token_budget=args.token_budget,
        )
    finally:
        svc.close()


COMMANDS = {
    "save": _cmd_save,
    "recall": _cmd_recall,
    "status": _cmd_status,
    "remember": _cmd_remember,
    "context": _cmd_context,
}


def _add_global_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--repo-id", default="default")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--db", default=".ai/memory/memory.db")
    ap.add_argument("--enable-vector", action="store_true")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="memory", description="Repo-local memory service")
    _add_global_args(ap)

    sub = ap.add_subparsers(dest="cmd", required=True)

    p_save = sub.add_parser("save", help="Save a memory (decision, pattern, learning, etc.)")
    p_save.add_argument("content", help="The memory content to save")
    p_save.add_argument("--type", choices=sorted(MEMORY_TYPES), default="learning")
    p_save.add_argument("--tags", help="Comma-separated tags")
    p_save.add_argument("--title", help="Short title (auto-derived if omitted)")
    p_save.add_argument("--agent", help="Agent identifier")
    p_save.add_argument("--task", help="Current task description")
    p_save.add_argument("--record-id", help="Update existing record by ID")

    p_recall = sub.add_parser("recall", help="Search memory for relevant context")
    p_recall.add_argument("query", help="What to search for")
    p_recall.add_argument("--limit", type=int, default=5)

    sub.add_parser("status", help="Show memory overview")

    p_remember = sub.add_parser("remember", help="Register and index file(s)")
    p_remember.add_argument("files", nargs="+", help="File path(s) to register")
    p_remember.add_argument("--kind", default="doc")

    p_context = sub.add_parser("context", help="Build context bundle for an objective")
    p_context.add_argument("objective", help="What you are trying to accomplish")
    p_context.add_argument("--profile", default="implementer",
                           choices=["generic", "implementer", "reviewer", "planner", "foreman"])
    p_context.add_argument("--token-budget", type=int)

    return ap


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        out = COMMANDS[args.cmd](args)
        print(json.dumps({"ok": True, "result": out}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "command": args.cmd}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
