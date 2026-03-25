from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .service import MemoryService, ServiceConfig


def load_json_arg(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    if value.startswith("@"):
        p = Path(value[1:])
        return json.loads(p.read_text(encoding="utf-8"))
    return json.loads(value)


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="memory", description="Repo-local memory service CLI")
    ap.add_argument("--repo-id", default="default")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--db", default=".ai/memory/memory.db")
    ap.add_argument("--enable-vector", action="store_true")

    sub = ap.add_subparsers(dest="cmd", required=True)

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


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    svc = MemoryService(
        ServiceConfig(
            repo_id=args.repo_id,
            repo_root=Path(args.repo_root).resolve(),
            db_path=Path(args.db).resolve(),
            enable_vector=bool(args.enable_vector),
        )
    )

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
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "command": args.cmd}, ensure_ascii=False, indent=2))
        return 1
    finally:
        svc.close()


if __name__ == "__main__":
    raise SystemExit(run())
