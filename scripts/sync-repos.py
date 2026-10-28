#!/usr/bin/env python3
"""Automated Builder Synchronization Pipeline.

Propagates updates, features, and bug fixes from the upstream
tplink-router-builder monorepo to the downstream official distributions:
  - tplink-cli (CLI tool, REPL, network optimization scripts)
  - tplink-mcp (Model Context Protocol server for AI agents)

Author: Dulith Divisekara (SLIIT Malabe)
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUILDER_DIR = Path("/home/dulith/Projects/tplink-router-builder")
CLI_DIR = Path("/home/dulith/Projects/tplink-cli")
MCP_DIR = Path("/home/dulith/Projects/tplink-mcp")


def run_cmd(cmd, cwd=None, check=True):
    print(f"\033[94m[EXEC]\033[0m {' '.join(cmd) if isinstance(cmd, list) else cmd} (in {cwd or '.'})")
    res = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"\033[91m[ERROR]\033[0m Command failed with code {res.returncode}:\n{res.stderr}")
        sys.exit(res.returncode)
    return res


def sync_cli():
    print("\n=======================================================")
    print("  Syncing to Downstream: tplink-cli")
    print("=======================================================")
    if not CLI_DIR.exists():
        print(f"Error: {CLI_DIR} does not exist.")
        return False

    # Sync core modules
    for mod in ["core", "clients", "models", "cli"]:
        src = BUILDER_DIR / "tplink_router" / mod
        dst = CLI_DIR / "tplink_cli" / mod
        if src.exists():
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)

    # Sync scripts and tests
    shutil.copy2(BUILDER_DIR / "scripts" / "optimize-network.sh", CLI_DIR / "scripts" / "optimize-network.sh")
    shutil.copy2(BUILDER_DIR / "scripts" / "keepalive-pulse.sh", CLI_DIR / "scripts" / "keepalive-pulse.sh")
    for t in (BUILDER_DIR / "tests").glob("test_*.py"):
        shutil.copy2(t, CLI_DIR / "tests" / t.name)

    # Rewrite imports from tplink_router to tplink_cli
    for py_file in CLI_DIR.glob("**/*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "tplink_router" in content:
            py_file.write_text(content.replace("tplink_router", "tplink_cli"), encoding="utf-8")

    # Run tests in tplink-cli
    print("Running unit tests in tplink-cli...")
    run_cmd(["python3", "-m", "unittest", "discover", "tests"], cwd=CLI_DIR)
    print("\033[92m[✓] tplink-cli sync and tests PASSED.\033[0m")
    return True


def sync_mcp():
    print("\n=======================================================")
    print("  Syncing to Downstream: tplink-mcp")
    print("=======================================================")
    if not MCP_DIR.exists():
        print(f"Error: {MCP_DIR} does not exist.")
        return False

    # Sync core modules
    for mod in ["core", "clients", "models"]:
        src = BUILDER_DIR / "tplink_router" / mod
        dst = MCP_DIR / "tplink_mcp" / mod
        if src.exists():
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)

    # Sync server.py
    shutil.copy2(BUILDER_DIR / "tplink_router" / "mcp" / "server.py", MCP_DIR / "tplink_mcp" / "server.py")

    # Sync tests
    for t in (BUILDER_DIR / "tests").glob("test_*.py"):
        shutil.copy2(t, MCP_DIR / "tests" / t.name)

    # Rewrite imports from tplink_router to tplink_mcp
    for py_file in MCP_DIR.glob("**/*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "tplink_router" in content:
            py_file.write_text(content.replace("tplink_router", "tplink_mcp"), encoding="utf-8")

    # Run tests in tplink-mcp
    print("Running unit tests in tplink-mcp...")
    run_cmd(["python3", "-m", "unittest", "discover", "tests"], cwd=MCP_DIR)
    print("\033[92m[✓] tplink-mcp sync and tests PASSED.\033[0m")
    return True


def main():
    parser = argparse.ArgumentParser(description="Synchronize upstream builder monorepo to downstream repositories.")
    parser.add_argument("--push", action="store_true", help="Automatically commit and push changes to remote repositories.")
    parser.add_argument("-m", "--message", default="sync: Propagate core updates from upstream builder", help="Git commit message")
    args = parser.parse_args()

    # 1. Test builder monorepo first
    print("\nVerifying upstream builder monorepo tests...")
    run_cmd(["python3", "-m", "unittest", "discover", "tests"], cwd=BUILDER_DIR)

    # 2. Sync CLI
    sync_cli()

    # 3. Sync MCP
    sync_mcp()

    # 4. Optional Push
    if args.push:
        print("\nStaging and pushing changes to downstreams...")
        for name, repo_path in [("tplink-cli", CLI_DIR), ("tplink-mcp", MCP_DIR)]:
            status = run_cmd(["git", "status", "--porcelain"], cwd=repo_path).stdout.strip()
            if status:
                print(f"Committing changes in {name}...")
                run_cmd(["git", "add", "."], cwd=repo_path)
                run_cmd(["git", "commit", "-m", args.message], cwd=repo_path)
                run_cmd(["git", "push", "origin", "main"], cwd=repo_path)
                print(f"\033[92m[✓] {name} pushed to GitHub.\033[0m")
            else:
                print(f"No unstaged changes in {name}.")

    print("\n\033[92m=======================================================")
    print("  All repositories synchronized and verified successfully!")
    print("=======================================================\033[0m\n")


if __name__ == "__main__":
    main()
