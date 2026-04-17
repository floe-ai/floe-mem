import { describe, it, expect, afterEach } from "bun:test";
import { existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomBytes } from "node:crypto";

const REPO_ROOT = join(import.meta.dir, "..");
const INSTALLER = join(REPO_ROOT, "install", "floe-mem.mjs");

function tempDir(): string {
  return join(tmpdir(), `floe-install-test-${randomBytes(6).toString("hex")}`);
}

async function runInstaller(args: string[], env?: Record<string, string>): Promise<{
  stdout: string;
  stderr: string;
  exitCode: number | null;
}> {
  const proc = Bun.spawn(["bun", INSTALLER, ...args], {
    stdout: "pipe",
    stderr: "pipe",
    env: { ...process.env, ...env },
  });
  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ]);
  return { stdout, stderr, exitCode };
}

describe("floe-mem installer", () => {
  const tmpDirs: string[] = [];

  afterEach(() => {
    for (const dir of tmpDirs) {
      rmSync(dir, { recursive: true, force: true });
    }
    tmpDirs.length = 0;
  });

  it("installs the canonical runtime and selected project target", async () => {
    const root = tempDir();
    tmpDirs.push(root);
    mkdirSync(root, { recursive: true });

    const { exitCode, stderr } = await runInstaller([
      "--project-root", root,
      "--target", "codex",
      "--yes",
      "--non-interactive",
    ]);

    expect(exitCode).toBe(0);
    expect(stderr).toBe("");
    expect(existsSync(join(root, ".floe", "memory", "scripts", "memory.ts"))).toBe(true);
    expect(existsSync(join(root, ".agents", "skills", "context-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(root, ".github", "skills", "context-memory", "SKILL.md"))).toBe(false);
    expect(existsSync(join(root, ".claude", "skills", "context-memory", "SKILL.md"))).toBe(false);
  });

  it("installs all targets when --target is omitted", async () => {
    const root = tempDir();
    tmpDirs.push(root);
    mkdirSync(root, { recursive: true });

    const { exitCode } = await runInstaller([
      "--project-root", root,
      "--yes",
      "--non-interactive",
    ]);

    expect(exitCode).toBe(0);
    expect(existsSync(join(root, ".floe", "memory", "scripts", "memory.ts"))).toBe(true);
    expect(existsSync(join(root, ".agents", "skills", "context-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(root, ".github", "skills", "context-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(root, ".claude", "skills", "context-memory", "SKILL.md"))).toBe(true);
  });

  it("copies skill markdown that points agents at the canonical runtime", async () => {
    const root = tempDir();
    tmpDirs.push(root);
    mkdirSync(root, { recursive: true });

    const { exitCode } = await runInstaller([
      "--project-root", root,
      "--target", "codex",
      "--yes",
      "--non-interactive",
    ]);

    expect(exitCode).toBe(0);
    const skill = readFileSync(join(root, ".agents", "skills", "context-memory", "SKILL.md"), "utf8");
    expect(skill).toContain(".floe/memory/scripts/memory.ts");
    expect(existsSync(join(root, ".agents", "skills", "context-memory", "scripts", "memory.ts"))).toBe(false);
  });

  it("fails if the install already exists without --force", async () => {
    const root = tempDir();
    tmpDirs.push(root);
    mkdirSync(root, { recursive: true });

    await runInstaller([
      "--project-root", root,
      "--target", "copilot",
      "--yes",
      "--non-interactive",
    ]);

    const { exitCode, stderr } = await runInstaller([
      "--project-root", root,
      "--target", "copilot",
      "--yes",
      "--non-interactive",
    ]);

    expect(exitCode).toBe(1);
    expect(stderr).toContain("Destination already exists");
  });

  it("overwrites an existing install with --force", async () => {
    const root = tempDir();
    tmpDirs.push(root);
    mkdirSync(root, { recursive: true });

    await runInstaller([
      "--project-root", root,
      "--target", "codex",
      "--yes",
      "--non-interactive",
    ]);

    const { exitCode } = await runInstaller([
      "--project-root", root,
      "--target", "codex",
      "--force",
      "--yes",
      "--non-interactive",
    ]);

    expect(exitCode).toBe(0);
  });

  it("installs global mode into the home-scoped Floe root and dotfolders", async () => {
    const root = tempDir();
    const home = join(root, "home");
    const projectRoot = join(root, "project");
    tmpDirs.push(root);
    mkdirSync(home, { recursive: true });
    mkdirSync(projectRoot, { recursive: true });

    const { exitCode } = await runInstaller([
      "--mode", "global",
      "--project-root", projectRoot,
      "--target", "codex,claude",
      "--yes",
      "--non-interactive",
    ], { HOME: home });

    expect(exitCode).toBe(0);
    expect(existsSync(join(home, ".floe", "memory", "scripts", "memory.ts"))).toBe(true);
    expect(existsSync(join(home, ".agents", "skills", "context-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(home, ".claude", "skills", "context-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(home, ".github", "skills", "context-memory", "SKILL.md"))).toBe(false);
    expect(existsSync(join(projectRoot, ".floe", "memory"))).toBe(false);
  });
});
