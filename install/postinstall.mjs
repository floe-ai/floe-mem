#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { run } from "./floe-mem.mjs";

async function main() {
  if (process.env.FLOE_MEM_SKIP_POSTINSTALL === "1") {
    return;
  }

  const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const initCwd = process.env.INIT_CWD?.trim() ? resolve(process.env.INIT_CWD) : null;

  // Auto-bootstrap only when floe-mem is being consumed as a dependency.
  if (!packageRoot.includes(`${process.platform === "win32" ? "\\" : "/"}node_modules${process.platform === "win32" ? "\\" : "/"}`)) {
    return;
  }

  if (!initCwd || initCwd === packageRoot) {
    return;
  }

  const initPackageJson = resolve(initCwd, "package.json");
  if (existsSync(initPackageJson)) {
    try {
      const initPackage = JSON.parse(readFileSync(initPackageJson, "utf8"));
      if (initPackage?.name === "floe-mem") {
        return;
      }
    } catch {
      // Ignore invalid package.json files and fall through to bootstrap.
    }
  }

  const args = ["--project-root", initCwd];
  // Default to interactive bootstrap; callers can force non-interactive mode.
  if (process.env.FLOE_MEM_NON_INTERACTIVE === "1") {
    args.push("--non-interactive");
  }

  await run(args, process.env);
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Error: ${message}`);
  process.exitCode = 1;
});
