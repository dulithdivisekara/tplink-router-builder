#!/usr/bin/env python3
"""Static Site Builder & Validator for TP-Link CLI Showcase.

Reads `data/metadata.json`, `data/commands.json`, and `data/benchmarks.json`,
validates schemas, and pre-renders static HTML for GitHub Pages and Cloudflare Pages.

Author: Dulith Divisekara (SLIIT Malabe)
"""

import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
METADATA_FILE = DATA_DIR / "metadata.json"
COMMANDS_FILE = DATA_DIR / "commands.json"
BENCHMARKS_FILE = DATA_DIR / "benchmarks.json"
HTML_FILE = ROOT_DIR / "index.html"


def validate_data():
    print(f"Validating {METADATA_FILE.name}...")
    if not METADATA_FILE.exists():
        raise FileNotFoundError(f"Missing {METADATA_FILE}")
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        meta = json.load(f)

    print(f"Validating {BENCHMARKS_FILE.name}...")
    if not BENCHMARKS_FILE.exists():
        raise FileNotFoundError(f"Missing {BENCHMARKS_FILE}")
    with open(BENCHMARKS_FILE, "r", encoding="utf-8") as f:
        benchmarks = json.load(f)

    print(f"Validating {COMMANDS_FILE.name}...")
    if not COMMANDS_FILE.exists():
        raise FileNotFoundError(f"Missing {COMMANDS_FILE}")
    with open(COMMANDS_FILE, "r", encoding="utf-8") as f:
        commands = json.load(f)
    assert isinstance(commands, list), "commands.json must be a JSON array"
    assert len(commands) >= 30, f"Expected at least 30 commands, found {len(commands)}"

    for c in commands:
        assert "name" in c, f"Command missing 'name': {c}"
        assert "command" in c, f"Command {c['name']} missing 'command'"
        assert "category" in c, f"Command {c['name']} missing 'category'"
        assert "description" in c, f"Command {c['name']} missing 'description'"

    print(f"Successfully validated {len(commands)} subcommands and metadata v{meta['version']}.")
    return meta, commands, benchmarks


def render_command_html(c):
    badge_colors = {
        "Diagnostics": "bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-300",
        "Cellular": "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-300",
        "SMS": "bg-purple-100 text-purple-900 dark:bg-purple-900/40 dark:text-purple-300",
        "Wi-Fi": "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-300",
        "System": "bg-rose-100 text-rose-900 dark:bg-rose-900/40 dark:text-rose-300",
        "Tuning": "bg-teal-100 text-teal-900 dark:bg-teal-900/40 dark:text-teal-300",
        "Interactive": "bg-cyan-100 text-cyan-900 dark:bg-cyan-900/40 dark:text-cyan-300",
    }
    badge_class = badge_colors.get(c.get("category", "Diagnostics"), "bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-300")

    flags_html = ""
    flags = c.get("flags", [])
    if flags:
        flag_tags = "".join([f'<span class="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-xs font-mono text-slate-700 dark:text-slate-300">{f}</span>' for f in flags[:3]])
        if len(flags) > 3:
            flag_tags += f'<span class="text-xs font-mono text-slate-500">+{len(flags)-3}</span>'
        flags_html = f'<div class="flex flex-wrap items-center gap-1.5 mt-3 pt-2.5 border-t border-slate-200 dark:border-slate-800">{flag_tags}</div>'

    return f"""        <div class="rounded-xl p-5 bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 cmd-card group transition-all duration-150" data-cmd="{c['name']}" data-cat="{c['category']}">
          <div class="flex items-center justify-between mb-2.5 gap-2">
            <code class="text-teal-700 dark:text-tplink-cyan text-sm font-bold font-mono group-hover:underline break-all">{c['command']}</code>
            <span class="shrink-0 px-2.5 py-0.5 rounded text-xs font-sans font-semibold {badge_class}">{c['category']}</span>
          </div>
          <p class="text-slate-700 dark:text-slate-300 text-sm leading-relaxed">{c['description']}</p>
          {flags_html}
        </div>"""


def build():
    meta, commands, benchmarks = validate_data()
    print("Pre-rendering commands into index.html...")

    if not HTML_FILE.exists():
        print(f"Warning: {HTML_FILE} does not exist yet. Will create.")
        return

    content = HTML_FILE.read_text(encoding="utf-8")

    grid_html = "\n".join([render_command_html(c) for c in commands])

    start_tag = '<!-- COMMANDS_GRID_START -->'
    end_tag = '<!-- COMMANDS_GRID_END -->'
    if start_tag in content and end_tag in content:
        parts = content.split(start_tag)
        pre = parts[0] + start_tag + "\n"
        post = "\n        " + end_tag + parts[1].split(end_tag)[1]
        new_content = pre + grid_html + post
        HTML_FILE.write_text(new_content, encoding="utf-8")
        print(f"[✓] Successfully injected {len(commands)} pre-rendered subcommands into {HTML_FILE.name}")
    else:
        print("Note: COMMANDS_GRID markers not found in index.html; client-side JS hydration will render dynamically.")


if __name__ == "__main__":
    build()
