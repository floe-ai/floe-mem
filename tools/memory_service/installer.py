from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from InquirerPy import inquirer

SKILL_NAME = "context-memory"
CLIENTS = ("codex", "copilot", "claude")
SCOPES = ("project", "global")


@dataclass(frozen=True)
class InstallTarget:
    client: str
    scope: str
    target_dir: Path


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_skill_dir() -> Path:
    repo_candidate = _package_root() / "skills" / SKILL_NAME
    if repo_candidate.exists():
        return repo_candidate
    packaged_candidate = Path(__file__).resolve().parents[1] / "bundled_skills" / SKILL_NAME
    if packaged_candidate.exists():
        return packaged_candidate
    return repo_candidate


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


def _tooling_root_for_target(target: InstallTarget, project_root: Path) -> Path:
    if target.scope == "project":
        return project_root
    if target.scope == "global":
        home = _global_home()
        if target.client == "codex":
            return home / ".agents"
        if target.client == "copilot":
            return home / ".copilot"
        if target.client == "claude":
            return home / ".claude"
    raise ValueError(f"unsupported client/scope for tooling root: {target.client}/{target.scope}")


def _print_err(message: str) -> None:
    print(message, file=sys.stderr)


def _is_tty() -> bool:
    return hasattr(sys.stdin, "isatty") and sys.stdin.isatty()


def _read_stdin(prompt: str = "> ") -> str:
    _print_err(prompt)
    line = sys.stdin.readline()
    return line.strip()


def _interactive_select_clients() -> list[str]:
    if _is_tty():
        choices = [
            {"name": "Codex", "value": "codex", "enabled": True},
            {"name": "Copilot", "value": "copilot", "enabled": True},
            {"name": "Claude", "value": "claude", "enabled": True},
        ]
        picked = inquirer.checkbox(
            message="Select target clients:",
            choices=choices,
            instruction="(↑↓ move, space toggle, enter confirm)",
            validate=lambda result: len(result) > 0,
            invalid_message="At least one client must be selected.",
        ).execute()
        if not picked:
            raise ValueError("at least one client must be selected")
        return picked

    # Fallback for non-TTY (piped input, CI, etc.)
    _print_err("Select target clients (comma-separated numbers, default: all):")
    _print_err("  1) Codex")
    _print_err("  2) Copilot")
    _print_err("  3) Claude")
    raw = _read_stdin()
    if not raw:
        return list(CLIENTS)
    index_map = {"1": "codex", "2": "copilot", "3": "claude"}
    picked_fallback: list[str] = []
    for token in [t.strip().lower() for t in raw.split(",") if t.strip()]:
        value = index_map.get(token, token)
        if value not in CLIENTS:
            raise ValueError(f"unknown client selection '{token}'")
        if value not in picked_fallback:
            picked_fallback.append(value)
    if not picked_fallback:
        raise ValueError("at least one client must be selected")
    return picked_fallback


def _interactive_select_scope() -> str:
    if _is_tty():
        scope = inquirer.select(
            message="Install scope:",
            choices=[
                {"name": "project (recommended)", "value": "project"},
                {"name": "global", "value": "global"},
            ],
            default="project",
        ).execute()
        return scope

    # Fallback for non-TTY
    _print_err("Install scope:")
    _print_err("  1) project (recommended)")
    _print_err("  2) global")
    raw = _read_stdin().lower()
    if raw in ("", "1", "project"):
        return "project"
    if raw in ("2", "global"):
        return "global"
    raise ValueError(f"unknown scope selection '{raw}'")


def _short_path(path: Path) -> str:
    """Return path relative to home if inside it, otherwise absolute."""
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return str(path)


def _interactive_confirm(targets: list[InstallTarget], scope: str, force: bool) -> bool:
    _print_err("")
    _print_err("  context-memory skill will be installed for:")
    _print_err("")
    for target in targets:
        _print_err(f"    {target.client.capitalize():10s}  →  {_short_path(target.target_dir)}")
    if force:
        _print_err("")
        _print_err("  Existing installations will be replaced (--force).")
    _print_err("")

    if _is_tty():
        return inquirer.confirm(
            message="Proceed with installation?",
            default=True,
        ).execute()

    # Fallback for non-TTY
    _print_err("Proceed with installation? [Y/n]")
    raw = _read_stdin().lower()
    return raw in ("", "y", "yes")


def _remove_existing(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path)


def _install_one(
    source_skill_dir: Path,
    source_repo_root: Path,
    target: InstallTarget,
    force: bool,
    project_root: Path,
    tooling_actions: dict[str, str],
) -> dict[str, Any]:
    target_dir = target.target_dir
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    if target_dir.exists() or target_dir.is_symlink():
        if not force:
            raise FileExistsError(f"target already exists: {target_dir}")
        _remove_existing(target_dir)

    shutil.copytree(source_skill_dir, target_dir)
    engine_dir, engine_action = _ensure_tooling_snapshot(
        source_repo_root=source_repo_root,
        target=target,
        project_root=project_root,
        force=force,
        tooling_actions=tooling_actions,
    )

    return {
        "client": target.client,
        "scope": target.scope,
        "target_dir": str(target_dir),
        "mode_requested": "copy",
        "mode_used": "copy",
        "tooling_dir": str(engine_dir),
        "tooling_action": engine_action,
        "status": "installed",
    }


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _ensure_tooling_snapshot(
    source_repo_root: Path,
    target: InstallTarget,
    project_root: Path,
    force: bool,
    tooling_actions: dict[str, str],
) -> tuple[Path, str]:
    tooling_root = _tooling_root_for_target(target=target, project_root=project_root)
    tools_pkg_dir = tooling_root / "tools"
    tools_pkg_dir.mkdir(parents=True, exist_ok=True)
    source_tools_init = source_repo_root / "tools" / "__init__.py"
    target_tools_init = tools_pkg_dir / "__init__.py"
    if not target_tools_init.exists() or force:
        _copy_file(source_tools_init, target_tools_init)

    source_engine_dir = source_repo_root / "tools" / "memory_service"
    target_engine_dir = tools_pkg_dir / "memory_service"
    key = str(target_engine_dir)
    if key in tooling_actions:
        return target_engine_dir, "reused_in_run"

    if target_engine_dir.exists():
        if force:
            _remove_existing(target_engine_dir)
            shutil.copytree(source_engine_dir, target_engine_dir, ignore=shutil.ignore_patterns("assets"))
            tooling_actions[key] = "replaced"
            return target_engine_dir, "replaced"
        tooling_actions[key] = "kept_existing"
        return target_engine_dir, "kept_existing"

    shutil.copytree(source_engine_dir, target_engine_dir, ignore=shutil.ignore_patterns("assets"))
    tooling_actions[key] = "created"
    return target_engine_dir, "created"


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install/sync context-memory skill for Codex, Copilot, and Claude")
    parser.add_argument("--target", help="comma-separated: codex,copilot,claude")
    parser.add_argument("--scope", choices=SCOPES)
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
        interactive = not args.non_interactive

        if interactive:
            clients = clients or _interactive_select_clients()
            scope = scope or _interactive_select_scope()
        else:
            clients = clients or list(CLIENTS)
            scope = scope or "project"

        if scope is None:
            raise ValueError("scope is required")

        project_root = _project_root(args.project_root)
        targets = _build_targets(clients, scope, project_root)

        if interactive and not args.yes:
            if not _interactive_confirm(targets=targets, scope=scope, force=bool(args.force)):
                print(json.dumps({"ok": False, "cancelled": True}, ensure_ascii=False, indent=2))
                return 1

        results: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        tooling_actions: dict[str, str] = {}
        for target in targets:
            try:
                result = _install_one(
                    source_skill_dir=source_skill_dir,
                    source_repo_root=source_repo_root,
                    target=target,
                    force=bool(args.force),
                    project_root=project_root,
                    tooling_actions=tooling_actions,
                )
                results.append(result)
            except Exception as exc:
                failures.append(
                    {
                        "client": target.client,
                        "scope": target.scope,
                        "target_dir": str(target.target_dir),
                        "mode_requested": "copy",
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
