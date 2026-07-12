#!/usr/bin/env node
"use strict";

const { execSync, execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const REPO_URL = "https://github.com/rajmaurya0904/bhav.git";
const MIN_PY_MINOR = 11; // require Python 3.11+

function log(msg) {
  console.log(msg);
}

function run(cmd, args, cwd) {
  // npm/npx are .cmd shims on Windows; CreateProcess can't exec those directly,
  // so they need shell:true there. Args are always our own hardcoded constants
  // (never user input), so unescaped shell interpolation is not a risk here.
  const needsShell = process.platform === "win32" && (cmd === "npm" || cmd === "npx");
  execFileSync(cmd, args, { cwd, stdio: "inherit", shell: needsShell });
}

function tryVersion(cmd) {
  try {
    const out = execSync(`${cmd} --version`, { stdio: ["ignore", "pipe", "pipe"] })
      .toString()
      .trim();
    return out;
  } catch {
    return null;
  }
}

function findPython() {
  for (const cmd of ["python3", "python", "py"]) {
    const out = tryVersion(cmd);
    if (!out) continue;
    const match = out.match(/(\d+)\.(\d+)/);
    if (!match) continue;
    const [, major, minor] = match;
    return { cmd, major: Number(major), minor: Number(minor), raw: out };
  }
  return null;
}

function main() {
  const target = process.argv[2] || "bhav";
  const targetPath = path.resolve(process.cwd(), target);

  log(`\nBhav — open-source NSE options backtesting engine\n`);

  if (fs.existsSync(targetPath) && fs.readdirSync(targetPath).length > 0) {
    console.error(`Error: "${target}" already exists and is not empty. Pick a different directory name.`);
    process.exit(1);
  }

  if (!tryVersion("git")) {
    console.error("Error: git is required but was not found on PATH. Install git and try again.");
    process.exit(1);
  }

  const python = findPython();
  if (!python) {
    console.error("Error: Python was not found on PATH. Install Python 3.11+ and try again.");
    process.exit(1);
  }
  if (python.major < 3 || (python.major === 3 && python.minor < MIN_PY_MINOR)) {
    log(`Warning: found ${python.raw}, but Bhav needs Python 3.${MIN_PY_MINOR}+. Continuing anyway — install may fail.`);
  } else {
    log(`Found ${python.raw}`);
  }

  log(`Cloning ${REPO_URL} into ./${target} ...`);
  run("git", ["clone", "--depth", "1", REPO_URL, targetPath]);

  log(`\nInstalling Python package (bhav CLI + API server) ...`);
  run(python.cmd, ["-m", "pip", "install", "-e", "."], targetPath);

  const frontendPath = path.join(targetPath, "frontend");
  if (fs.existsSync(frontendPath)) {
    log(`\nInstalling frontend dependencies ...`);
    run("npm", ["install"], frontendPath);
  }

  log(`
Done. Bhav is set up in ./${target}

Next steps:
  cd ${target}

  # get a fresh Upstox access token (expires daily ~03:30 IST) and set it:
  set UPSTOX_TOKEN=your_token          (cmd.exe)
  $env:UPSTOX_TOKEN = "your_token"     (PowerShell)
  export UPSTOX_TOKEN=your_token       (bash)

  # run a strategy from the CLI:
  bhav run examples/orb_v1.py --start 2025-08-01 --end 2025-11-30

  # or start the full web UI:
  bhav-server                          (terminal 1: API on :8000)
  cd frontend && npm run dev           (terminal 2: UI on :3000)

Docs: ${targetPath}${path.sep}docs${path.sep}writing-strategies.md
`);
}

main();
