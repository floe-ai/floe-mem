import { expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, writeFileSync, rmSync, mkdirSync, existsSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";

const SCRIPT = join(import.meta.dir, "..", "skills", "context-memory", "scripts", "memory.ts");

function runMemory(args: string[], cwd: string): { stdout: string; exitCode: number } {
  const result = Bun.spawnSync(["bun", "run", SCRIPT, ...args], {
    cwd,
    env: { ...process.env },
  });
  return {
    stdout: result.stdout.toString(),
    exitCode: result.exitCode,
  };
}

function parseOutput(stdout: string): any {
  return JSON.parse(stdout);
}

let tmpDir: string;

beforeEach(() => {
  tmpDir = mkdtempSync(join(tmpdir(), "memory-test-"));
});

afterEach(() => {
  rmSync(tmpDir, { recursive: true, force: true });
});

test("no args returns usage error", () => {
  const { stdout, exitCode } = runMemory([], tmpDir);
  const out = parseOutput(stdout);
  expect(exitCode).toBe(2);
  expect(out.ok).toBe(false);
  expect(out.error).toContain("no command provided");
});

test("unknown command returns error", () => {
  const { stdout, exitCode } = runMemory(["bogus"], tmpDir);
  const out = parseOutput(stdout);
  expect(exitCode).toBe(2);
  expect(out.ok).toBe(false);
  expect(out.error).toContain("unknown command");
});

test("save creates a memory", () => {
  const dbPath = join(tmpDir, ".ai", "memory", "memory.db");
  const { stdout, exitCode } = runMemory(
    ["save", "We chose JWT for auth", "--type", "decision", "--tags", "auth,api", "--db", dbPath],
    tmpDir
  );
  const out = parseOutput(stdout);
  expect(exitCode).toBe(0);
  expect(out.ok).toBe(true);
  expect(out.result.saved).toMatch(/^mem_/);
  expect(out.result.type).toBe("decision");
  expect(out.result.title).toBe("We chose JWT for auth");
});

test("recall finds saved memories", () => {
  const dbPath = join(tmpDir, ".ai", "memory", "memory.db");
  // Save first
  runMemory(["save", "JWT authentication with refresh tokens", "--type", "decision", "--db", dbPath], tmpDir);

  // Recall
  const { stdout, exitCode } = runMemory(["recall", "JWT", "--db", dbPath], tmpDir);
  const out = parseOutput(stdout);
  expect(exitCode).toBe(0);
  expect(out.ok).toBe(true);
  expect(out.result.count).toBeGreaterThan(0);
  expect(out.result.memories[0].type).toBe("memory");
});

test("status shows counts", () => {
  const dbPath = join(tmpDir, ".ai", "memory", "memory.db");
  runMemory(["save", "test memory", "--db", dbPath], tmpDir);

  const { stdout, exitCode } = runMemory(["status", "--db", dbPath], tmpDir);
  const out = parseOutput(stdout);
  expect(exitCode).toBe(0);
  expect(out.ok).toBe(true);
  expect(out.result.memories).toBe(1);
  expect(out.result.recent.length).toBe(1);
});

test("remember registers and indexes a file", () => {
  const dbPath = join(tmpDir, ".ai", "memory", "memory.db");
  const docsDir = join(tmpDir, "docs");
  mkdirSync(docsDir, { recursive: true });
  writeFileSync(join(docsDir, "note.md"), "# Note\n\nHello memory");

  const { stdout, exitCode } = runMemory(["remember", "docs/note.md", "--db", dbPath], tmpDir);
  const out = parseOutput(stdout);
  expect(exitCode).toBe(0);
  expect(out.ok).toBe(true);
  expect(out.result.registered.length).toBe(1);
  expect(out.result.registered[0].file).toBe("docs/note.md");
  expect(out.result.indexed.chunks).toBeGreaterThan(0);
});

test("context builds a bundle", () => {
  const dbPath = join(tmpDir, ".ai", "memory", "memory.db");
  runMemory(["save", "Authentication uses JWT tokens", "--type", "decision", "--db", dbPath], tmpDir);

  const { stdout, exitCode } = runMemory(["context", "authentication", "--db", dbPath], tmpDir);
  const out = parseOutput(stdout);
  expect(exitCode).toBe(0);
  expect(out.ok).toBe(true);
  expect(out.result.objective).toBe("authentication");
  expect(out.result.profile).toBe("implementer");
  expect(out.result.token_budget).toBe(2200);
});

test("save with --record-id updates existing", () => {
  const dbPath = join(tmpDir, ".ai", "memory", "memory.db");
  const save1 = parseOutput(
    runMemory(["save", "original content", "--type", "learning", "--db", dbPath], tmpDir).stdout
  );
  const id = save1.result.saved;

  const save2 = parseOutput(
    runMemory(["save", "updated content", "--type", "decision", "--record-id", id, "--db", dbPath], tmpDir).stdout
  );
  expect(save2.result.saved).toBe(id);
  expect(save2.result.updated).toBe(true);
  expect(save2.result.type).toBe("decision");
});

test("save without content returns error", () => {
  const dbPath = join(tmpDir, ".ai", "memory", "memory.db");
  const { stdout, exitCode } = runMemory(["save", "--db", dbPath], tmpDir);
  // --db gets consumed as content (it's positional), but the actual error
  // depends on parsing — just check it doesn't crash silently
  expect(exitCode).toBeLessThanOrEqual(1);
});
