#!/usr/bin/env node
/**
 * Start the backend: create venv + install deps if missing, then run uvicorn.
 */
import { spawnSync, spawn } from "child_process";
import { existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const backend = join(root, "backend");
const isWin = process.platform === "win32";
const venvBin = join(backend, "venv", isWin ? "Scripts" : "bin");
const venvPython = join(venvBin, isWin ? "python.exe" : "python");
const venvPip = join(venvBin, isWin ? "pip.exe" : "pip");
const requirements = join(backend, "requirements.txt");

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", cwd: backend, ...opts });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

// Ensure venv exists
if (!existsSync(venvPython)) {
  console.log("Backend venv not found. Creating venv and installing dependencies...");
  run("python3", ["-m", "venv", "venv"]);
  if (existsSync(requirements)) {
    run(venvPip, ["install", "-r", "requirements.txt"]);
  }
  console.log("Backend venv ready.");
}

// Start uvicorn (inherits stdio so logs show in terminal)
const proc = spawn(
  venvPython,
  ["-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
  { stdio: "inherit", cwd: backend }
);
proc.on("exit", (code) => process.exit(code ?? 0));
