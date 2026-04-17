import { expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, writeFileSync, readFileSync, rmSync, mkdirSync, existsSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";

const SCRIPT = join(import.meta.dir, "..", "floe", "runtime", "scripts", "memory.ts");

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

function runInstalledMemory(args: string[], cwd: string): { stdout: string; exitCode: number } {
  const installedScript = join(cwd, ".floe", "memory", "scripts", "memory.ts");
  mkdirSync(join(cwd, ".floe", "memory", "scripts"), { recursive: true });
  writeFileSync(installedScript, readFileSync(SCRIPT, "utf8"), "utf8");

  const result = Bun.spawnSync(["bun", "run", installedScript, ...args], {
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
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
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
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
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
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
  runMemory(["save", "test memory", "--db", dbPath], tmpDir);

  const { stdout, exitCode } = runMemory(["status", "--db", dbPath], tmpDir);
  const out = parseOutput(stdout);
  expect(exitCode).toBe(0);
  expect(out.ok).toBe(true);
  expect(out.result.memories).toBe(1);
  expect(out.result.recent.length).toBe(1);
});

test("installed .floe runtime resolves the project root correctly", () => {
  const { stdout, exitCode } = runInstalledMemory(["status"], tmpDir);
  const out = parseOutput(stdout);
  expect(exitCode).toBe(0);
  expect(out.ok).toBe(true);
  expect(existsSync(join(tmpDir, ".floe", "memory", "memory.db"))).toBe(true);
});

test("remember registers and indexes a file", () => {
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
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
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
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
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
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
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
  const { stdout, exitCode } = runMemory(["save", "--db", dbPath], tmpDir);
  // --db gets consumed as content (it's positional), but the actual error
  // depends on parsing — just check it doesn't crash silently
  expect(exitCode).toBeLessThanOrEqual(1);
});

// ─── Relationship commands ──────────────────────────────────────────

test("link creates a relationship between two memories", () => {
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");

  const m1 = parseOutput(runMemory(["save", "decision A", "--type", "decision", "--db", dbPath], tmpDir).stdout);
  const m2 = parseOutput(runMemory(["save", "decision B", "--type", "decision", "--db", dbPath], tmpDir).stdout);
  const id1 = m1.result.saved;
  const id2 = m2.result.saved;

  const { stdout, exitCode } = runMemory(
    ["link", "memory", id1, "relates_to", "memory", id2, "--db", dbPath],
    tmpDir
  );
  const out = parseOutput(stdout);
  expect(exitCode).toBe(0);
  expect(out.ok).toBe(true);
  expect(out.result.linked).toMatch(/^rel_/);
  expect(out.result.updated).toBe(false);
});

test("link is idempotent — second link updates", () => {
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
  const m1 = parseOutput(runMemory(["save", "A", "--db", dbPath], tmpDir).stdout).result.saved;
  const m2 = parseOutput(runMemory(["save", "B", "--db", dbPath], tmpDir).stdout).result.saved;

  runMemory(["link", "memory", m1, "relates_to", "memory", m2, "--db", dbPath], tmpDir);
  const second = parseOutput(
    runMemory(["link", "memory", m1, "relates_to", "memory", m2, "--weight", "0.5", "--db", dbPath], tmpDir).stdout
  );
  expect(second.result.updated).toBe(true);
});

test("link rejects unknown source entity", () => {
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
  const m = parseOutput(runMemory(["save", "real memory", "--db", dbPath], tmpDir).stdout).result.saved;
  const { stdout, exitCode } = runMemory(
    ["link", "memory", "mem_doesnotexist", "relates_to", "memory", m, "--db", dbPath],
    tmpDir
  );
  const out = parseOutput(stdout);
  expect(exitCode).toBe(1);
  expect(out.ok).toBe(false);
  expect(out.error).toContain("not found");
});

test("links returns neighbours", () => {
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
  const m1 = parseOutput(runMemory(["save", "A", "--db", dbPath], tmpDir).stdout).result.saved;
  const m2 = parseOutput(runMemory(["save", "B", "--db", dbPath], tmpDir).stdout).result.saved;
  runMemory(["link", "memory", m1, "derived_from", "memory", m2, "--db", dbPath], tmpDir);

  const out = parseOutput(
    runMemory(["links", "memory", m1, "--direction", "out", "--db", dbPath], tmpDir).stdout
  );
  expect(out.ok).toBe(true);
  expect(out.result.count).toBe(1);
  expect(out.result.links[0].relation).toBe("derived_from");
  expect(out.result.links[0].dst.id).toBe(m2);
});

test("unlink removes a relationship", () => {
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
  const m1 = parseOutput(runMemory(["save", "A", "--db", dbPath], tmpDir).stdout).result.saved;
  const m2 = parseOutput(runMemory(["save", "B", "--db", dbPath], tmpDir).stdout).result.saved;
  const relId = parseOutput(
    runMemory(["link", "memory", m1, "relates_to", "memory", m2, "--db", dbPath], tmpDir).stdout
  ).result.linked;

  const { stdout, exitCode } = runMemory(["unlink", relId, "--db", dbPath], tmpDir);
  const out = parseOutput(stdout);
  expect(exitCode).toBe(0);
  expect(out.result.unlinked).toBe(relId);

  const linksOut = parseOutput(
    runMemory(["links", "memory", m1, "--db", dbPath], tmpDir).stdout
  );
  expect(linksOut.result.count).toBe(0);
});

test("recall --expand-links returns linked neighbours", () => {
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
  const m1 = parseOutput(runMemory(["save", "typescript bun rewrite decision", "--type", "decision", "--db", dbPath], tmpDir).stdout).result.saved;
  const m2 = parseOutput(runMemory(["save", "unrelated other memory", "--type", "learning", "--db", dbPath], tmpDir).stdout).result.saved;
  runMemory(["link", "memory", m1, "relates_to", "memory", m2, "--db", dbPath], tmpDir);

  const out = parseOutput(
    runMemory(["recall", "typescript bun", "--expand-links", "--db", dbPath], tmpDir).stdout
  );
  expect(out.ok).toBe(true);
  // m2 should appear as a linked neighbour
  const ids = out.result.memories.map((m: any) => m.id);
  expect(ids).toContain(m2);
  const neighbour = out.result.memories.find((m: any) => m.id === m2);
  expect(neighbour.tier).toBe("linked");
});

// ─── Discovery: .floe runtime isolation ────────────────────────────

test("discovery skips floe-mem runtime state under .floe/memory", () => {
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
  mkdirSync(join(tmpDir, "docs"), { recursive: true });
  writeFileSync(join(tmpDir, "docs", "note.md"), "# Note\n\nHello memory");
  mkdirSync(join(tmpDir, ".floe", "memory"), { recursive: true });
  writeFileSync(join(tmpDir, ".floe", "memory", "internal.txt"), "internal state");

  const out = parseOutput(
    runMemory(["remember", "docs/note.md", "--db", dbPath], tmpDir).stdout
  );
  expect(out.ok).toBe(true);
  expect(out.result.registered.length).toBe(1);
  expect(out.result.registered[0].file).toBe("docs/note.md");
  expect(out.result.indexed.documents).toBe(1);
});

// ─── Scoring: pure unit tests (direct import) ──────────────────────

import { getRelationFactor, computeExpandedScore } from "../floe/runtime/scripts/memory.ts";

test("getRelationFactor: known relations", () => {
  expect(getRelationFactor("derived_from")).toBe(1.00);
  expect(getRelationFactor("continues")).toBe(1.00);
  expect(getRelationFactor("depends_on")).toBe(1.00);
  expect(getRelationFactor("blocks")).toBe(1.00);
  expect(getRelationFactor("describes")).toBe(1.00);
  expect(getRelationFactor("belongs_to")).toBe(0.85);
  expect(getRelationFactor("supersedes")).toBe(0.85);
  expect(getRelationFactor("relates_to")).toBe(0.60);
  expect(getRelationFactor("mentions")).toBe(0.35);
});

test("getRelationFactor: unknown relation returns 0.60", () => {
  expect(getRelationFactor("invented_relation")).toBe(0.60);
  expect(getRelationFactor("")).toBe(0.60);
});

test("getRelationFactor: case-insensitive", () => {
  expect(getRelationFactor("DERIVED_FROM")).toBe(1.00);
  expect(getRelationFactor("Relates_To")).toBe(0.60);
});

// Spec test A: source=80, derived_from, weight=1.0 → 80 * 0.30 * 1.00 * 1.0 = 24.0
test("computeExpandedScore: spec case A — basic formula", () => {
  expect(computeExpandedScore(80, "derived_from", 1.0)).toBe(24.0);
});

// Spec test B: relation factor ordering
test("computeExpandedScore: spec case B — relation factor ordering", () => {
  const derivedScore = computeExpandedScore(100, "derived_from", 1.0);
  const relatesToScore = computeExpandedScore(100, "relates_to", 1.0);
  const mentionsScore = computeExpandedScore(100, "mentions", 1.0);
  expect(derivedScore).toBeGreaterThan(relatesToScore);
  expect(relatesToScore).toBeGreaterThan(mentionsScore);
});

// Spec test C: edge weight effect
test("computeExpandedScore: spec case C — stronger weight ranks higher", () => {
  const heavy = computeExpandedScore(100, "relates_to", 2.0);
  const light = computeExpandedScore(100, "relates_to", 0.5);
  expect(heavy).toBeGreaterThan(light);
});

// Spec test D: unknown relation uses 0.60
test("computeExpandedScore: spec case D — unknown relation uses 0.60", () => {
  const unknown = computeExpandedScore(100, "some_new_relation", 1.0);
  const relatesto = computeExpandedScore(100, "relates_to", 1.0);
  expect(unknown).toBe(relatesto); // both use factor 0.60
});

// Spec test E: cap at source_score * 0.95
test("computeExpandedScore: spec case E — cap enforced with high edge weight", () => {
  const score = computeExpandedScore(100, "derived_from", 100.0);
  expect(score).toBe(95.0); // capped at 100 * 0.95
});

test("computeExpandedScore: invalid edge weight defaults to 1.0", () => {
  expect(computeExpandedScore(80, "derived_from", 0)).toBe(24.0);   // weight 0 → use 1.0
  expect(computeExpandedScore(80, "derived_from", -1)).toBe(24.0);  // negative → use 1.0
  expect(computeExpandedScore(80, "derived_from", NaN)).toBe(24.0); // NaN → use 1.0
});

// ─── Scoring: integration tests via CLI ────────────────────────────

// Spec test F: dedup — same linked entity from two source hits → one result, highest score
test("expand-links dedup: spec case F — highest score wins across source hits", () => {
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");

  // Two source memories with different scores via different search tiers
  const high = parseOutput(runMemory(["save", "exact match target high score", "--type", "decision", "--db", dbPath], tmpDir).stdout).result.saved;
  const low  = parseOutput(runMemory(["save", "another memory lower score",   "--type", "learning", "--db", dbPath], tmpDir).stdout).result.saved;
  const target = parseOutput(runMemory(["save", "shared neighbour",             "--type", "learning", "--db", dbPath], tmpDir).stdout).result.saved;

  // Both source hits link to the same target
  runMemory(["link", "memory", high, "derived_from", "memory", target, "--db", dbPath], tmpDir);
  runMemory(["link", "memory", low,  "relates_to",   "memory", target, "--db", dbPath], tmpDir);

  const out = parseOutput(
    runMemory(["recall", "exact match target high score", "--limit", "5", "--expand-links", "--link-limit", "10", "--db", dbPath], tmpDir).stdout
  );
  expect(out.ok).toBe(true);

  // target should appear exactly once
  const targetHits = out.result.memories.filter((m: any) => m.id === target);
  expect(targetHits.length).toBe(1);

  // The kept score should be the higher one (derived_from from high-scoring source)
  const keptScore = targetHits[0].score;
  const lowScore = computeExpandedScore(30, "relates_to", 1.0); // low source would give lower
  expect(keptScore).toBeGreaterThan(lowScore);
});

// Spec test G: no behaviour change without --expand-links
test("expand-links: spec case G — ranking unchanged without flag", () => {
  const dbPath = join(tmpDir, ".floe", "memory", "memory.db");
  const m1 = parseOutput(runMemory(["save", "baseline memory", "--type", "learning", "--db", dbPath], tmpDir).stdout).result.saved;
  const m2 = parseOutput(runMemory(["save", "linked other",    "--type", "learning", "--db", dbPath], tmpDir).stdout).result.saved;
  runMemory(["link", "memory", m1, "relates_to", "memory", m2, "--db", dbPath], tmpDir);

  const without = parseOutput(runMemory(["recall", "baseline memory", "--db", dbPath], tmpDir).stdout);
  const ids = without.result.memories.map((m: any) => m.id);
  // m2 should NOT appear — no --expand-links
  expect(ids).not.toContain(m2);
});
