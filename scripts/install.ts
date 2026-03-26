#!/usr/bin/env bun
/**
 * floe-mem installer — invoked via:
 *   bunx github:floe-ai/floe-mem
 *
 * Copies the context-memory skill into one or more agent client directories.
 * Supports Codex (.agents/), Copilot (.github/), and Claude (.claude/).
 *
 * Prerequisites: bun, git
 */

import { existsSync, mkdirSync, rmSync, cpSync } from "node:fs";
import { resolve, join } from "node:path";
import { createInterface } from "node:readline";
import { homedir } from "node:os";
import { parseArgs } from "node:util";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SKILL_NAME = "context-memory";
const CLIENTS = ["codex", "copilot", "claude"] as const;
type Client = (typeof CLIENTS)[number];

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

/** Directory this script lives in — works at runtime and via bunx cache */
const SCRIPT_DIR = import.meta.dir;

/** Root of the floe-mem package (one level up from scripts/) */
const PACKAGE_ROOT = resolve(SCRIPT_DIR, "..");

function skillSourceDir(): string {
  const candidate = join(PACKAGE_ROOT, "skills", SKILL_NAME);
  if (existsSync(candidate)) return candidate;
  throw new Error(`skill source not found at: ${candidate}`);
}

function targetDir(client: Client, projectRoot: string): string {
  const dirs: Record<Client, string> = {
    codex: join(projectRoot, ".agents", "skills", SKILL_NAME),
    copilot: join(projectRoot, ".github", "skills", SKILL_NAME),
    claude: join(projectRoot, ".claude", "skills", SKILL_NAME),
  };
  return dirs[client];
}

function shortPath(p: string): string {
  const home = homedir();
  return p.startsWith(home) ? `~${p.slice(home.length)}` : p;
}

// ---------------------------------------------------------------------------
// Interactive prompts (readline, zero deps)
// ---------------------------------------------------------------------------

function ask(rl: ReturnType<typeof createInterface>, question: string): Promise<string> {
  return new Promise((resolve) => rl.question(question, resolve));
}

async function selectClients(rl: ReturnType<typeof createInterface>): Promise<Client[]> {
  console.log("\nSelect target clients (comma-separated, or press Enter for all):");
  CLIENTS.forEach((c, i) => console.log(`  ${i + 1}) ${c}`));
  const raw = await ask(rl, "> ");
  if (!raw.trim()) return [...CLIENTS];
  const picked: Client[] = [];
  for (const token of raw.split(",").map((t) => t.trim().toLowerCase())) {
    const byIndex = CLIENTS[parseInt(token, 10) - 1];
    const byName = CLIENTS.find((c) => c === token);
    const resolved = byIndex ?? byName;
    if (!resolved) throw new Error(`unknown client: '${token}'`);
    if (!picked.includes(resolved)) picked.push(resolved);
  }
  if (picked.length === 0) throw new Error("at least one client must be selected");
  return picked;
}

async function confirm(rl: ReturnType<typeof createInterface>, message: string): Promise<boolean> {
  const raw = (await ask(rl, `${message} [Y/n] `)).trim().toLowerCase();
  return raw === "" || raw === "y" || raw === "yes";
}

// ---------------------------------------------------------------------------
// Installation
// ---------------------------------------------------------------------------

interface InstallResult {
  client: Client;
  targetDir: string;
  status: "installed" | "skipped" | "failed";
  error?: string;
}

function installOne(source: string, dest: string, force: boolean): void {
  if (existsSync(dest)) {
    if (!force) throw new Error(`already exists: ${dest} (use --force to overwrite)`);
    rmSync(dest, { recursive: true, force: true });
  }
  mkdirSync(resolve(dest, ".."), { recursive: true });
  cpSync(source, dest, { recursive: true });
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

async function main() {
  const { values } = parseArgs({
    args: Bun.argv.slice(2),
    options: {
      target: { type: "string" },
      "project-root": { type: "string" },
      force: { type: "boolean", default: false },
      yes: { type: "boolean", default: false },
      "non-interactive": { type: "boolean", default: false },
    },
    allowPositionals: true,
    strict: false,
  });

  const nonInteractive = Boolean(values["non-interactive"]);
  const projectRoot = resolve(
    (values["project-root"] as string | undefined) ?? process.cwd()
  );

  const rl = createInterface({ input: process.stdin, output: process.stdout });

  try {
    let clients: Client[];

    if (nonInteractive || !process.stdout.isTTY) {
      const rawTarget = values["target"] as string | undefined;
      clients = rawTarget
        ? (rawTarget.split(",").map((t) => t.trim().toLowerCase()) as Client[])
        : [...CLIENTS];
    } else {
      clients =
        values["target"] != null
          ? (values["target"].split(",").map((t) => t.trim().toLowerCase()) as Client[])
          : await selectClients(rl);
    }

    const source = skillSourceDir();
    const targets = clients.map((c) => ({
      client: c,
      dir: targetDir(c, projectRoot),
    }));

    if (!values["yes"] && process.stdout.isTTY) {
      console.log(`\n  context-memory will be installed for:\n`);
      for (const t of targets) {
        console.log(`    ${t.client.padEnd(10)}  →  ${shortPath(t.dir)}`);
      }
      if (values["force"]) console.log("\n  Existing installations will be replaced (--force).");
      console.log("");
      const ok = await confirm(rl, "Proceed?");
      if (!ok) {
        console.log("Cancelled.");
        process.exit(1);
      }
    }

    const results: InstallResult[] = [];
    for (const t of targets) {
      try {
        installOne(source, t.dir, Boolean(values["force"]));
        results.push({ client: t.client, targetDir: t.dir, status: "installed" });
        console.log(`  ✓ ${t.client.padEnd(10)} → ${shortPath(t.dir)}`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        results.push({ client: t.client, targetDir: t.dir, status: "failed", error: msg });
        console.error(`  ✗ ${t.client.padEnd(10)} → ${msg}`);
      }
    }

    const failures = results.filter((r) => r.status === "failed");
    if (failures.length > 0) {
      console.error(`\n${failures.length} installation(s) failed.`);
      process.exit(1);
    }

    console.log(`\n✓ ${results.length} installation(s) complete.`);
    console.log("  Agents can now use: bun run scripts/memory.ts <command>");
  } finally {
    rl.close();
  }
}

main().catch((err) => {
  console.error("Error:", err instanceof Error ? err.message : String(err));
  process.exit(1);
});
