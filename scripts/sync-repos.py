#!/usr/bin/env python3
"""Central Hub Synchronization & Deployment Orchestrator.

Propagates updates, features, and bug fixes from the upstream
tplink-router-builder monorepo hub to all 4 downstream official distributions:
  1. tplink-cli (CLI tool, REPL, network optimization scripts, deb, brew, npm)
  2. tplink-mcp (Model Context Protocol server for AI agents)
  3. tp-link-cli-web (Developer web showcase for tplink-cli.dulith.me)
  4. tp-link-mcp-web (Official MCP schema catalog for tp-link-mcp.dulith.me)

Author: Dulith Divisekara (SLIIT Malabe)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUILDER_DIR = Path("/home/dulith/Projects/tplink-router-builder")
CLI_DIR = Path("/home/dulith/Projects/tplink-cli")
MCP_DIR = Path("/home/dulith/Projects/tplink-mcp")
CLI_WEB_DIR = Path("/home/dulith/Projects/tp-link-cli-web")
MCP_WEB_DIR = Path("/home/dulith/Projects/tp-link-mcp-web")


def run_cmd(cmd, cwd=None, check=True):
    print(f"\033[94m[EXEC]\033[0m {' '.join(cmd) if isinstance(cmd, list) else cmd} (in {cwd or '.'})")
    res = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"\033[91m[ERROR]\033[0m Command failed with code {res.returncode}:\n{res.stderr}")
        sys.exit(res.returncode)
    return res


def sync_cli():
    print("\n=======================================================")
    print("  [1/4] Syncing Downstream Package: tplink-cli")
    print("=======================================================")
    if not CLI_DIR.exists():
        print(f"Error: {CLI_DIR} does not exist.")
        return False

    # Sync core modules
    for mod in ["core", "clients", "models", "cli", "calibration"]:
        src = BUILDER_DIR / "tplink_router" / mod
        dst = CLI_DIR / "tplink_cli" / mod
        if src.exists():
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)

    # Sync scripts and tests
    (CLI_DIR / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILDER_DIR / "scripts" / "optimize-network.sh", CLI_DIR / "scripts" / "optimize-network.sh")
    shutil.copy2(BUILDER_DIR / "scripts" / "keepalive-pulse.sh", CLI_DIR / "scripts" / "keepalive-pulse.sh")
    shutil.copy2(BUILDER_DIR / "scripts" / "router_calibrator.py", CLI_DIR / "scripts" / "router_calibrator.py")
    for t in (BUILDER_DIR / "tests").glob("test_*.py"):
        if t.name == "test_mcp_server.py":
            continue
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
    print("  [2/4] Syncing Downstream Package: tplink-mcp")
    print("=======================================================")
    if not MCP_DIR.exists():
        print(f"Error: {MCP_DIR} does not exist.")
        return False

    # Sync core modules
    for mod in ["core", "clients", "models", "calibration"]:
        src = BUILDER_DIR / "tplink_router" / mod
        dst = MCP_DIR / "tplink_mcp" / mod
        if src.exists():
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)

    # Sync server.py
    shutil.copy2(BUILDER_DIR / "tplink_router" / "mcp" / "server.py", MCP_DIR / "tplink_mcp" / "server.py")

    # Sync tests
    for t in (BUILDER_DIR / "tests").glob("test_*.py"):
        if t.name.startswith("test_cli"):
            continue
        shutil.copy2(t, MCP_DIR / "tests" / t.name)

    # Rewrite imports from tplink_router to tplink_mcp
    for py_file in MCP_DIR.glob("**/*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "tplink_router.mcp.server" in content:
            content = content.replace("tplink_router.mcp.server", "tplink_mcp.server")
        if "tplink_router" in content:
            content = content.replace("tplink_router", "tplink_mcp")
        py_file.write_text(content, encoding="utf-8")

    # Run tests in tplink-mcp
    print("Running unit tests in tplink-mcp...")
    run_cmd(["python3", "-m", "unittest", "discover", "tests"], cwd=MCP_DIR)
    print("\033[92m[✓] tplink-mcp sync and tests PASSED.\033[0m")
    return True


def sync_cli_web():
    print("\n=======================================================")
    print("  [3/4] Syncing Downstream Web Showcase: tp-link-cli-web")
    print("=======================================================")
    if not CLI_WEB_DIR.exists():
        print(f"Warning: {CLI_WEB_DIR} does not exist.")
        return False

    # Sync install script and deb package if present in CLI repo
    if (CLI_DIR / "install.sh").exists():
        shutil.copy2(CLI_DIR / "install.sh", CLI_WEB_DIR / "install.sh")
    if (CLI_DIR / "web" / "tplink-cli_1.0.0_all.deb").exists():
        shutil.copy2(CLI_DIR / "web" / "tplink-cli_1.0.0_all.deb", CLI_WEB_DIR / "tplink-cli_1.0.0_all.deb")

    # Build Debian APT repository
    apt_script = CLI_WEB_DIR / "scripts" / "build-apt-repo.py"
    if apt_script.exists():
        print("Building Debian APT repository in tp-link-cli-web...")
        run_cmd(["python3", str(apt_script)], cwd=CLI_WEB_DIR)

    # Run build script to validate schemas and pre-render
    print("Running build script in tp-link-cli-web...")
    run_cmd(["python3", "scripts/build.py"], cwd=CLI_WEB_DIR)
    print("\033[92m[✓] tp-link-cli-web sync and pre-rendering PASSED.\033[0m")
    return True


def sync_mcp_web():
    print("\n=======================================================")
    print("  [4/4] Syncing Downstream Web Showcase: tp-link-mcp-web")
    print("=======================================================")
    if not MCP_WEB_DIR.exists():
        print(f"Warning: {MCP_WEB_DIR} does not exist.")
        return False

    # Run build script to validate schemas and pre-render
    print("Running build script in tp-link-mcp-web...")
    run_cmd(["python3", "scripts/build.py"], cwd=MCP_WEB_DIR)
    print("\033[92m[✓] tp-link-mcp-web sync and pre-rendering PASSED.\033[0m")
    return True


def bump_version(ver):
    print(f"\nBumping version across all repositories to {ver}...")
    for repo, meta_file in [
        (MCP_WEB_DIR, MCP_WEB_DIR / "data" / "metadata.json"),
        (CLI_WEB_DIR, CLI_WEB_DIR / "data" / "metadata.json"),
    ]:
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            d["version"] = ver
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2)
            print(f"Updated {meta_file}")


def deploy_web_showcases():
    print("\n=======================================================")
    print("  Deploying Web Showcases to Cloudflare Pages")
    print("=======================================================")
    print("Deploying tp-link-mcp-web -> tp-link-mcp.dulith.me...")
    run_cmd([
        "npx", "wrangler", "pages", "deploy", str(MCP_WEB_DIR),
        "--project-name", "tp-link-mcp", "--branch", "main", "--commit-dirty=true"
    ])

    print("Deploying tp-link-cli-web -> tp-link-cli.dulith.me...")
    run_cmd([
        "npx", "wrangler", "pages", "deploy", str(CLI_WEB_DIR),
        "--project-name", "tp-link-cli", "--branch", "main", "--commit-dirty=true"
    ])
    print("\033[92m[✓] Both web showcases deployed live successfully!\033[0m")


def main():
    parser = argparse.ArgumentParser(description="Synchronize upstream builder hub to all 4 downstream repositories.")
    parser.add_argument("--push", action="store_true", help="Automatically commit and push changes across all 4 downstreams.")
    parser.add_argument("--deploy", action="store_true", help="Deploy updated web showcases to Cloudflare Pages.")
    parser.add_argument("--bump-version", type=str, help="Bump version string across all packages and web metadata.")
    parser.add_argument("-m", "--message", default="sync: Propagate core updates from upstream builder hub", help="Git commit message")
    args = parser.parse_args()

    if args.bump_version:
        bump_version(args.bump_version)

    # 1. Test builder monorepo first
    print("\nVerifying upstream builder monorepo tests...")
    run_cmd(["python3", "-m", "unittest", "discover", "tests"], cwd=BUILDER_DIR)

    # 2. Extract catalog
    catalog_script = BUILDER_DIR / "scripts" / "extract-catalog.py"
    if catalog_script.exists():
        run_cmd(["python3", str(catalog_script)], cwd=BUILDER_DIR)

    # 3. Sync all 4 downstreams
    sync_cli()
    sync_mcp()
    sync_cli_web()
    sync_mcp_web()

    # 4. Optional Push to Git
    if args.push:
        print("\nStaging and pushing changes across downstream repositories...")
        repos = [
            ("tplink-cli", CLI_DIR),
            ("tplink-mcp", MCP_DIR),
            ("tp-link-cli-web", CLI_WEB_DIR),
            ("tp-link-mcp-web", MCP_WEB_DIR),
        ]
        for name, repo_path in repos:
            if not repo_path.exists():
                continue
            status = run_cmd(["git", "status", "--porcelain"], cwd=repo_path).stdout.strip()
            if status:
                print(f"Committing changes in {name}...")
                run_cmd(["git", "add", "."], cwd=repo_path)
                run_cmd(["git", "commit", "-m", args.message], cwd=repo_path)
                run_cmd(["git", "push", "origin", "main"], cwd=repo_path)
                print(f"\033[92m[✓] {name} pushed to GitHub.\033[0m")
            else:
                print(f"No unstaged changes in {name}.")

    # 5. Optional Deploy to Cloudflare Pages
    if args.deploy:
        deploy_web_showcases()

    print("\n\033[92m=======================================================================")
    print("  Hub Orchestration Complete: All 4 repositories verified and in sync!")
    print("=======================================================================\033[0m\n")


if __name__ == "__main__":
    main()
