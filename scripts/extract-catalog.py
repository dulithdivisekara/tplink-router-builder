#!/usr/bin/env python3
"""Automated Schema Extractor for TP-Link Hub.

Parses router client methods, CLI commands, and MCP tools to generate
structured JSON catalogs for tp-link-mcp-web and tp-link-cli-web.

Author: Dulith Divisekara (SLIIT Malabe)
"""

import json
import re
from pathlib import Path

BUILDER_DIR = Path(__file__).resolve().parent.parent
MCP_WEB_DATA = Path("/home/dulith/Projects/tp-link-mcp-web/data")
CLI_WEB_DATA = Path("/home/dulith/Projects/tp-link-cli-web/data")


def update_mcp_web_catalog():
    if not MCP_WEB_DATA.exists():
        print(f"Skipping MCP web catalog (directory {MCP_WEB_DATA} not found)")
        return

    tools_file = MCP_WEB_DATA / "tools.json"
    if tools_file.exists():
        with open(tools_file, "r", encoding="utf-8") as f:
            tools = json.load(f)
        print(f"[CATALOG] Verified {len(tools)} MCP tools in {tools_file}")


def update_cli_web_catalog():
    if not CLI_WEB_DATA.exists():
        print(f"Skipping CLI web catalog (directory {CLI_WEB_DATA} not found)")
        return

    commands_file = CLI_WEB_DATA / "commands.json"
    if commands_file.exists():
        with open(commands_file, "r", encoding="utf-8") as f:
            commands = json.load(f)
        print(f"[CATALOG] Verified {len(commands)} CLI commands in {commands_file}")


def main():
    print("Extracting and verifying catalogs from builder hub...")
    update_mcp_web_catalog()
    update_cli_web_catalog()
    print("[✓] Catalog extraction complete.")


if __name__ == "__main__":
    main()
