import { describe, it, expect, afterEach } from "bun:test";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomBytes } from "node:crypto";

const REPO_ROOT = join(import.meta.dir, "..");
const INSTALLER = join(REPO_ROOT, "install", "floe-mem.mjs");
const POSTINSTALL = join(REPO_ROOT, "install", "postinstall.mjs");

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

async function runPostinstall(env?: Record<string, string>): Promise<{
  stdout: string;
  stderr: string;
  exitCode: number | null;
}> {
  const proc = Bun.spawn(["bun", POSTINSTALL], {
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

function stageDependencyInstall(root: string): string {
  const packageRoot = join(root, "node_modules", "floe-mem");
  mkdirSync(join(root, "node_modules"), { recursive: true });
  mkdirSync(packageRoot, { recursive: true });
  cpSync(join(REPO_ROOT, "package.json"), join(packageRoot, "package.json"), { force: true });
  cpSync(join(REPO_ROOT, "install"), join(packageRoot, "install"), { recursive: true });
  cpSync(join(REPO_ROOT, "floe"), join(packageRoot, "floe"), { recursive: true });
  cpSync(join(REPO_ROOT, "node_modules", "floe-boot"), join(root, "node_modules", "floe-boot"), {
    recursive: true,
  });
  cpSync(join(REPO_ROOT, "node_modules", "yaml"), join(root, "node_modules", "yaml"), {
    recursive: true,
  });
  cpSync(join(REPO_ROOT, "node_modules", "@clack"), join(root, "node_modules", "@clack"), {
    recursive: true,
  });
  cpSync(join(REPO_ROOT, "node_modules", "picocolors"), join(root, "node_modules", "picocolors"), {
    recursive: true,
  });
  cpSync(join(REPO_ROOT, "node_modules", "sisteransi"), join(root, "node_modules", "sisteransi"), {
    recursive: true,
  });
  return packageRoot;
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
    expect(existsSync(join(root, ".agents", "skills", "floe-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(root, ".github", "skills", "floe-memory", "SKILL.md"))).toBe(false);
    expect(existsSync(join(root, ".claude", "skills", "floe-memory", "SKILL.md"))).toBe(false);
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
    expect(existsSync(join(root, ".agents", "skills", "floe-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(root, ".github", "skills", "floe-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(root, ".claude", "skills", "floe-memory", "SKILL.md"))).toBe(true);
  });

  it("uses INIT_CWD as the default project root when none is passed", async () => {
    const root = tempDir();
    tmpDirs.push(root);
    mkdirSync(root, { recursive: true });

    const { exitCode } = await runInstaller([
      "--yes",
      "--non-interactive",
    ], { INIT_CWD: root });

    expect(exitCode).toBe(0);
    expect(existsSync(join(root, ".floe", "memory", "scripts", "memory.ts"))).toBe(true);
    expect(existsSync(join(root, ".agents", "skills", "floe-memory", "SKILL.md"))).toBe(true);
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
    const skill = readFileSync(join(root, ".agents", "skills", "floe-memory", "SKILL.md"), "utf8");
    expect(skill).toContain(".floe/memory/scripts/memory.ts");
    expect(existsSync(join(root, ".agents", "skills", "floe-memory", "scripts", "memory.ts"))).toBe(false);
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
    expect(existsSync(join(home, ".agents", "skills", "floe-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(home, ".claude", "skills", "floe-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(home, ".github", "skills", "floe-memory", "SKILL.md"))).toBe(false);
    expect(existsSync(join(projectRoot, ".floe", "memory"))).toBe(false);
  });

  it("postinstall bootstraps from INIT_CWD without requiring a target", async () => {
    const root = tempDir();
    const consumerRoot = join(root, "consumer");
    tmpDirs.push(root);
    mkdirSync(consumerRoot, { recursive: true });
    const packageRoot = stageDependencyInstall(consumerRoot);

    const proc = Bun.spawn(["node", join(packageRoot, "install", "postinstall.mjs")], {
      cwd: packageRoot,
      stdout: "pipe",
      stderr: "pipe",
      env: { ...process.env, INIT_CWD: consumerRoot },
    });
    const [, stderr, exitCode] = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
      proc.exited,
    ]);

    expect(exitCode).toBe(0);
    expect(stderr).toBe("");
    expect(existsSync(join(consumerRoot, ".floe", "memory", "scripts", "memory.ts"))).toBe(true);
    expect(existsSync(join(consumerRoot, ".agents", "skills", "floe-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(consumerRoot, ".github", "skills", "floe-memory", "SKILL.md"))).toBe(true);
    expect(existsSync(join(consumerRoot, ".claude", "skills", "floe-memory", "SKILL.md"))).toBe(true);
  });
});
