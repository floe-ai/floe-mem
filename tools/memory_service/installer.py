from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_NAME = "context-memory"
INSTALL_META_FILENAME = ".memory_skill_install.json"
CLIENTS = ("codex", "copilot", "claude")
SCOPES = ("project", "global")
MODES = ("auto", "symlink", "copy")


@dataclass(frozen=True)
class InstallTarget:
    client: str
    scope: str
    target_dir: Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_skill_dir() -> Path:
    return _package_root() / "skills" / SKILL_NAME


def _project_root(path_value: str | None) -> Path:
    if path_value:
        return Path(path_value).expanduser().resolve()
    return Path.cwd().resolve()


def _global_home() -> Path:
    return Path.home().resolve()


def _target_dir(client: str, scope: str, project_root: Path) -> Path:
    if scope == "project":
        if client == "codex":
            return project_root / ".agents" / "skills" / SKILL_NAME
        if client == "copilot":
            return project_root / ".github" / "skills" / SKILL_NAME
        if client == "claude":
            return project_root / ".claude" / "skills" / SKILL_NAME
    if scope == "global":
        home = _global_home()
        if client == "codex":
            return home / ".agents" / "skills" / SKILL_NAME
        if client == "copilot":
            return home / ".copilot" / "skills" / SKILL_NAME
        if client == "claude":
            return home / ".claude" / "skills" / SKILL_NAME
    raise ValueError(f"unsupported client/scope: {client}/{scope}")


def _print_err(message: str) -> None:
    print(message, file=sys.stderr)


def _read_stdin(prompt: str = "> ") -> str:
    _print_err(prompt)
    line = sys.stdin.readline()
    return line.strip()


def _interactive_select_clients() -> list[str]:
    _print_err("Select target clients (comma-separated numbers, default: all):")
    _print_err("  1) Codex")
    _print_err("  2) Copilot")
    _print_err("  3) Claude")
    raw = _read_stdin()
    if not raw:
        return list(CLIENTS)
    index_map = {"1": "codex", "2": "copilot", "3": "claude"}
    picked: list[str] = []
    for token in [t.strip().lower() for t in raw.split(",") if t.strip()]:
        if token in index_map:
            value = index_map[token]
        else:
            value = token
        if value not in CLIENTS:
            raise ValueError(f"unknown client selection '{token}'")
        if value not in picked:
            picked.append(value)
    if not picked:
        raise ValueError("at least one client must be selected")
    return picked


def _interactive_select_scope() -> str:
    _print_err("Install scope:")
    _print_err("  1) project (recommended)")
    _print_err("  2) global")
    raw = _read_stdin().lower()
    if raw in ("", "1", "project"):
        return "project"
    if raw in ("2", "global"):
        return "global"
    raise ValueError(f"unknown scope selection '{raw}'")


def _interactive_select_mode() -> str:
    _print_err("Install mode:")
    _print_err("  1) symlink (recommended)")
    _print_err("  2) copy")
    _print_err("Symlink keeps one source of truth and makes updates easier.")
    _print_err("Copy is more portable but can drift from source.")
    raw = _read_stdin().lower()
    if raw in ("", "1", "symlink"):
        return "symlink"
    if raw in ("2", "copy"):
        return "copy"
    raise ValueError(f"unknown mode selection '{raw}'")


def _interactive_confirm() -> bool:
    _print_err("Apply this installation plan? [y/N]")
    raw = _read_stdin().lower()
    return raw in ("y", "yes")


def _remove_existing(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path)


def _write_install_metadata(target_dir: Path, source_repo_root: Path, client: str, scope: str, mode_used: str) -> None:
    meta = {
        "skill_name": SKILL_NAME,
        "source_repo_root": str(source_repo_root),
        "installed_at": _now_iso(),
        "client": client,
        "scope": scope,
        "install_mode_used": mode_used,
    }
    (target_dir / INSTALL_META_FILENAME).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _install_one(
    source_skill_dir: Path,
    source_repo_root: Path,
    target: InstallTarget,
    mode: str,
    force: bool,
) -> dict[str, Any]:
    target_dir = target.target_dir
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    if target_dir.exists() or target_dir.is_symlink():
        if not force:
            raise FileExistsError(f"target already exists: {target_dir}")
        _remove_existing(target_dir)

    mode_used = mode
    if mode == "symlink":
        os.symlink(str(source_skill_dir), str(target_dir), target_is_directory=True)
    elif mode == "copy":
        shutil.copytree(source_skill_dir, target_dir)
    elif mode == "auto":
        try:
            os.symlink(str(source_skill_dir), str(target_dir), target_is_directory=True)
            mode_used = "symlink"
        except OSError:
            shutil.copytree(source_skill_dir, target_dir)
            mode_used = "copy"
    else:
        raise ValueError(f"invalid mode '{mode}'")

    if mode_used == "copy":
        _write_install_metadata(
            target_dir=target_dir,
            source_repo_root=source_repo_root,
            client=target.client,
            scope=target.scope,
            mode_used=mode_used,
        )

    return {
        "client": target.client,
        "scope": target.scope,
        "target_dir": str(target_dir),
        "mode_requested": mode,
        "mode_used": mode_used,
        "status": "installed",
    }


def _parse_targets(raw_target: str | None) -> list[str]:
    if not raw_target:
        return []
    out: list[str] = []
    for token in [t.strip().lower() for t in raw_target.split(",") if t.strip()]:
        if token not in CLIENTS:
            raise ValueError(f"unsupported client '{token}'")
        if token not in out:
            out.append(token)
    return out


def _build_targets(clients: list[str], scope: str, project_root: Path) -> list[InstallTarget]:
    return [InstallTarget(client=c, scope=scope, target_dir=_target_dir(c, scope, project_root)) for c in clients]


def _emit_plan(source_skill_dir: Path, targets: list[InstallTarget], mode: str, force: bool) -> None:
    _print_err(f"Source skill: {source_skill_dir}")
    _print_err(f"Install mode: {mode}")
    _print_err(f"Force replace: {'yes' if force else 'no'}")
    _print_err("Targets:")
    for target in targets:
        _print_err(f"  - {target.client}/{target.scope}: {target.target_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install/sync context-memory skill for Codex, Copilot, and Claude")
    parser.add_argument("--target", help="comma-separated: codex,copilot,claude")
    parser.add_argument("--scope", choices=SCOPES)
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--project-root", help="project root for project-scoped installs (default: cwd)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--yes", action="store_true", help="skip confirmation")
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args(argv)

    source_repo_root = _package_root()
    source_skill_dir = _canonical_skill_dir()
    if not source_skill_dir.exists():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"canonical skill source not found: {source_skill_dir}",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    try:
        clients = _parse_targets(args.target)
        scope = args.scope
        mode = args.mode
        interactive = not args.non_interactive and not (clients and scope and mode)

        if interactive:
            clients = clients or _interactive_select_clients()
            scope = scope or _interactive_select_scope()
            mode = mode or _interactive_select_mode()
        else:
            clients = clients or list(CLIENTS)
            scope = scope or "project"
            mode = mode or "auto"

        if scope is None or mode is None:
            raise ValueError("scope and mode are required")

        project_root = _project_root(args.project_root)
        targets = _build_targets(clients, scope, project_root)
        _emit_plan(source_skill_dir=source_skill_dir, targets=targets, mode=mode, force=bool(args.force))

        if interactive and not args.yes:
            if not _interactive_confirm():
                print(json.dumps({"ok": False, "cancelled": True}, ensure_ascii=False, indent=2))
                return 1

        results: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for target in targets:
            try:
                result = _install_one(
                    source_skill_dir=source_skill_dir,
                    source_repo_root=source_repo_root,
                    target=target,
                    mode=mode,
                    force=bool(args.force),
                )
                results.append(result)
            except Exception as exc:
                failures.append(
                    {
                        "client": target.client,
                        "scope": target.scope,
                        "target_dir": str(target.target_dir),
                        "mode_requested": mode,
                        "status": "failed",
                        "error": str(exc),
                    }
                )

        ok = len(failures) == 0
        print(
            json.dumps(
                {
                    "ok": ok,
                    "source_skill_dir": str(source_skill_dir),
                    "source_repo_root": str(source_repo_root),
                    "results": results,
                    "failures": failures,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if ok else 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
