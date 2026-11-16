#!/usr/bin/env node

/**
 * Universal Node.js CLI launcher for tplink-cli
 * Dispatches to Python tplink_router engine with argument forwarding.
 * Author: Dulith Divisekara (SLIIT Malabe)
 */

const { spawn } = require("child_process");
const path = require("path");

const rootDir = path.resolve(__dirname, "..");
const pythonScript = "-m";
const pythonModule = "tplink_router.cli.main";

const pythonBin = process.env.PYTHON_BIN || (process.platform === "win32" ? "python" : "python3");
const args = [pythonScript, pythonModule, ...process.argv.slice(2)];

const child = spawn(pythonBin, args, {
  cwd: rootDir,
  env: {
    ...process.env,
    PYTHONPATH: rootDir + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : ""),
  },
  stdio: "inherit",
});

child.on("error", (err) => {
  if (err.code === "ENOENT") {
    console.error(`[tplink-cli] Error: ${pythonBin} not found. Please ensure Python 3.10+ is installed.`);
  } else {
    console.error(`[tplink-cli] Execution failed:`, err);
  }
  process.exit(1);
});

child.on("close", (code) => {
  process.exit(code || 0);
});
