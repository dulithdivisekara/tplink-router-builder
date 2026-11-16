#!/usr/bin/env python3
"""Unified Static Site Builder & Validator for TP-Link Router Suite Web Portals.

Validates:
  1. CLI Showcase: web/cli/data/metadata.json, commands.json, benchmarks.json
  2. MCP Catalog: web/mcp/data/metadata.json, tools.json

Pre-renders dynamic HTML grids into:
  - web/cli/index.html
  - web/mcp/index.html

Author: Dulith Divisekara (SLIIT Malabe)
"""

import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CLI_DIR = ROOT_DIR / "cli"
MCP_DIR = ROOT_DIR / "mcp"


def build_cli():
    print("\n--- Validating & Building CLI Showcase (web/cli) ---")
    data_dir = CLI_DIR / "data"
    meta_file = data_dir / "metadata.json"
    commands_file = data_dir / "commands.json"
    benchmarks_file = data_dir / "benchmarks.json"
    html_file = CLI_DIR / "index.html"

    if not meta_file.exists() or not commands_file.exists() or not benchmarks_file.exists():
        raise FileNotFoundError(f"Missing CLI data files in {data_dir}")

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    with open(benchmarks_file, "r", encoding="utf-8") as f:
        benchmarks = json.load(f)
    with open(commands_file, "r", encoding="utf-8") as f:
        commands = json.load(f)

    assert isinstance(commands, list) and len(commands) >= 30, f"Expected >= 30 commands, found {len(commands)}"
    for c in commands:
        for k in ["name", "command", "category", "description"]:
            assert k in c, f"Command {c.get('name')} missing key {k}"

    print(f"Validated {len(commands)} CLI subcommands and metadata v{meta.get('version', '1.0.0')}.")

    if not html_file.exists():
        print(f"Warning: {html_file} does not exist.")
        return

    content = html_file.read_text(encoding="utf-8")

    category_colors = {
        "Telemetry": "bg-blue-500/10 text-blue-400 border-blue-500/20",
        "Cellular": "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
        "Network": "bg-purple-500/10 text-purple-400 border-purple-500/20",
        "Hardware": "bg-amber-500/10 text-amber-400 border-amber-500/20",
        "Diagnostics": "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
        "Administration": "bg-rose-500/10 text-rose-400 border-rose-500/20",
    }

    def render_cmd(c):
        badge_class = category_colors.get(c["category"], "bg-slate-500/10 text-slate-400 border-slate-500/20")
        flags_html = ""
        if "flags" in c and c["flags"]:
            tags = " ".join([f'<span class="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">{fl}</span>' for fl in c["flags"]])
            flags_html = f'<div class="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-slate-200 dark:border-slate-800">{tags}</div>'
        return f"""        <div class="rounded-xl p-5 bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 cmd-card group transition-all duration-150" data-cmd="{c['name']}" data-cat="{c['category']}">
          <div class="flex items-center justify-between mb-2.5 gap-2">
            <code class="text-teal-700 dark:text-tplink-cyan text-sm font-bold font-mono group-hover:underline break-all">{c['command']}</code>
            <span class="shrink-0 px-2.5 py-0.5 rounded text-xs font-sans font-semibold {badge_class}">{c['category']}</span>
          </div>
          <p class="text-slate-700 dark:text-slate-300 text-sm leading-relaxed">{c['description']}</p>
          {flags_html}
        </div>"""

    grid_html = "\n".join([render_cmd(c) for c in commands])
    start_tag = "<!-- COMMANDS_GRID_START -->"
    end_tag = "<!-- COMMANDS_GRID_END -->"
    if start_tag in content and end_tag in content:
        parts = content.split(start_tag)
        pre = parts[0] + start_tag + "\n"
        post = "\n        " + end_tag + parts[1].split(end_tag)[1]
        html_file.write_text(pre + grid_html + post, encoding="utf-8")
        print(f"[✓] Successfully injected {len(commands)} pre-rendered subcommands into {html_file.name}")
    else:
        print("Note: COMMANDS_GRID markers not found in index.html (client JS dynamic hydration active).")


def build_mcp():
    print("\n--- Validating & Building MCP Catalog (web/mcp) ---")
    data_dir = MCP_DIR / "data"
    meta_file = data_dir / "metadata.json"
    tools_file = data_dir / "tools.json"
    html_file = MCP_DIR / "index.html"

    if not meta_file.exists() or not tools_file.exists():
        raise FileNotFoundError(f"Missing MCP data files in {data_dir}")

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    with open(tools_file, "r", encoding="utf-8") as f:
        tools = json.load(f)

    assert isinstance(tools, list) and len(tools) >= 30, f"Expected >= 30 tools, found {len(tools)}"
    for t in tools:
        for k in ["name", "category", "description", "parameters"]:
            assert k in t, f"Tool {t.get('name')} missing key {k}"

    print(f"Validated {len(tools)} MCP tools and metadata v{meta.get('version', '1.0.0')}.")

    if not html_file.exists():
        print(f"Warning: {html_file} does not exist.")
        return

    content = html_file.read_text(encoding="utf-8")

    category_colors = {
        "Telemetry": "bg-blue-500/10 text-blue-400 border-blue-500/20",
        "Cellular": "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
        "Network": "bg-purple-500/10 text-purple-400 border-purple-500/20",
        "Hardware": "bg-amber-500/10 text-amber-400 border-amber-500/20",
        "Diagnostics": "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
        "Administration": "bg-rose-500/10 text-rose-400 border-rose-500/20",
    }

    def render_tool(t):
        badge_class = category_colors.get(t["category"], "bg-slate-500/10 text-slate-400 border-slate-500/20")
        param_count = len(t.get("parameters", []))
        param_text = f"{param_count} param{'s' if param_count != 1 else ''}" if param_count > 0 else "0 params"
        return f"""        <div class="rounded-xl p-5 bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 tool-card cursor-pointer group transition-all duration-150" data-name="{t['name']}" data-cat="{t['category']}" onclick="openToolModal('{t['name']}')">
          <div class="flex items-center justify-between mb-3 gap-2">
            <code class="text-sm font-bold font-mono text-teal-700 dark:text-tplink-cyan group-hover:underline break-all">{t['name']}</code>
            <span class="shrink-0 px-2.5 py-0.5 rounded text-xs font-sans font-semibold {badge_class}">{t['category']}</span>
          </div>
          <p class="text-slate-700 dark:text-slate-300 text-sm leading-relaxed mb-4">{t['description']}</p>
          <div class="flex items-center justify-between text-xs font-sans text-slate-500 dark:text-slate-400 border-t border-slate-200 dark:border-slate-800 pt-3">
            <span class="font-mono">{param_text}</span>
            <span class="text-teal-700 dark:text-tplink-cyan font-semibold group-hover:underline flex items-center gap-1">
              Inspect Schema
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </span>
          </div>
        </div>"""

    grid_html = "\n".join([render_tool(t) for t in tools])
    start_tag = "<!-- TOOLS_GRID_START -->"
    end_tag = "<!-- TOOLS_GRID_END -->"
    if start_tag in content and end_tag in content:
        parts = content.split(start_tag)
        pre = parts[0] + start_tag + "\n"
        post = "\n        " + end_tag + parts[1].split(end_tag)[1]
        html_file.write_text(pre + grid_html + post, encoding="utf-8")
        print(f"[✓] Successfully injected {len(tools)} pre-rendered tools into {html_file.name}")
    else:
        print("Note: TOOLS_GRID markers not found in index.html (client JS dynamic hydration active).")


def build_all():
    print("==================================================================")
    print("  TP-Link Router Suite - Unified Web Portal Builder")
    print("==================================================================")
    build_cli()
    build_mcp()
    print("\n[✓] All web portal components successfully validated and built!\n")


if __name__ == "__main__":
    build_all()
