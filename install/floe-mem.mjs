#!/usr/bin/env node

import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

function normalizeArgs(argv) {
  const normalized = [];

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];

    if (token === "--scope") {
      normalized.push("--mode");
      if (index + 1 < argv.length) {
        normalized.push(argv[index + 1]);
        index += 1;
      }
      continue;
    }

    normalized.push(token);
  }

  return normalized;
}

function applyDefaultProjectRoot(argv, env) {
  if (argv.includes("--project-root")) {
    return argv;
  }

  const initCwd = env.INIT_CWD?.trim();
  if (!initCwd) {
    return argv;
  }

  return ["--project-root", resolve(initCwd), ...argv];
}

export async function run(argv = process.argv.slice(2), env = process.env) {
  const manifestPath = resolve(dirname(fileURLToPath(import.meta.url)), "manifest.yml");
  const normalizedArgv = applyDefaultProjectRoot(normalizeArgs(argv), env);
  const args = normalizedArgv.includes("--manifest")
    ? normalizedArgv
    : ["--manifest", manifestPath, ...normalizedArgv];

  let main;
  try {
    ({ main } = await import("floe-boot/cli"));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`Error: floe-boot is required to run this installer. ${message}`);
    process.exitCode = 1;
    return;
  }

  try {
    await main(args);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`Error: ${message}`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  run();
}
