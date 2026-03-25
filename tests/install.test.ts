import { describe, it, expect, afterEach } from "bun:test";
import { existsSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomBytes } from "node:crypto";

const REPO_ROOT = join(import.meta.dir, "..");
const INSTALLER = join(REPO_ROOT, "scripts", "install.ts");

function tempDir(): string {
  const dir = join(tmpdir(), `floe-install-test-${randomBytes(6).toString("hex")}`);
  return dir;
}

async function runInstaller(args: string[], env?: Record<string, string>): Promise<{
  stdout: string;
  stderr: string;
  exitCode: number | null;
}> {
  const proc = Bun.spawn(
    ["bun", "run", INSTALLER, ...args],
    {
      stdout: "pipe",
      stderr: "pipe",
      env: { ...process.env, ...env },
    }
  );
  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ]);
  return { stdout, stderr, exitCode };
}

describe("install.ts", () => {
  const tmpDirs: string[] = [];

  afterEach(() => {
    for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
    tmpDirs.length = 0;
  });

  it("installs codex project-scope skill files", async () => {
    const root = tempDir();
    tmpDirs.push(root);

    const { exitCode, stderr } = await runInstaller([
      "--target", "codex",
      "--scope", "project",
      "--project-root", root,
      "--yes",
      "--non-interactive",
    ]);

    expect(exitCode).toBe(0);
    const skillDir = join(root, ".agents", "skills", "context-memory");
    expect(existsSync(skillDir)).toBe(true);
    expect(existsSync(join(skillDir, "SKILL.md"))).toBe(true);
    expect(existsSync(join(skillDir, "scripts", "memory.ts"))).toBe(true);
  });

  it("installs claude global-scope skill files", async () => {
    const home = tempDir();
    tmpDirs.push(home);

    const { exitCode } = await runInstaller([
      "--target", "claude",
      "--scope", "global",
      "--yes",
      "--non-interactive",
    ], { HOME: home });

    expect(exitCode).toBe(0);
    const skillDir = join(home, ".claude", "skills", "context-memory");
    expect(existsSync(skillDir)).toBe(true);
    expect(existsSync(join(skillDir, "SKILL.md"))).toBe(true);
    expect(existsSync(join(skillDir, "scripts", "memory.ts"))).toBe(true);
  });

  it("installs all clients when --target is omitted", async () => {
    const root = tempDir();
    tmpDirs.push(root);

    const { exitCode } = await runInstaller([
      "--scope", "project",
      "--project-root", root,
      "--yes",
      "--non-interactive",
    ]);

    expect(exitCode).toBe(0);
    for (const [client, dir] of [
      ["codex", ".agents"],
      ["copilot", ".github"],
      ["claude", ".claude"],
    ] as const) {
      const skillDir = join(root, dir, "skills", "context-memory");
      expect(existsSync(skillDir)).toBe(true);
    }
  });

  it("fails if destination exists without --force", async () => {
    const root = tempDir();
    tmpDirs.push(root);

    await runInstaller([
      "--target", "copilot",
      "--scope", "project",
      "--project-root", root,
      "--yes",
      "--non-interactive",
    ]);

    const { exitCode, stderr } = await runInstaller([
      "--target", "copilot",
      "--scope", "project",
      "--project-root", root,
      "--yes",
      "--non-interactive",
    ]);

    expect(exitCode).toBe(1);
    expect(stderr).toMatch(/already exists/);
  });

  it("overwrites with --force", async () => {
    const root = tempDir();
    tmpDirs.push(root);

    await runInstaller([
      "--target", "codex",
      "--scope", "project",
      "--project-root", root,
      "--yes",
      "--non-interactive",
    ]);

    const { exitCode } = await runInstaller([
      "--target", "codex",
      "--scope", "project",
      "--project-root", root,
      "--force",
      "--yes",
      "--non-interactive",
    ]);

    expect(exitCode).toBe(0);
  });

  it("does NOT copy tools/ directory to install target", async () => {
    const root = tempDir();
    tmpDirs.push(root);

    await runInstaller([
      "--target", "codex",
      "--scope", "project",
      "--project-root", root,
      "--yes",
      "--non-interactive",
    ]);

    expect(existsSync(join(root, "tools"))).toBe(false);
  });
});
