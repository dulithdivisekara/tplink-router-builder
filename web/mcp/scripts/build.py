#!/usr/bin/env python3
"""Static Site Builder & Validator for TP-Link MCP Showcase.

Reads `data/metadata.json` and `data/tools.json`, validates schemas,
and builds an optimized static web package for GitHub Pages and Cloudflare Pages.

Author: Dulith Divisekara (SLIIT Malabe)
"""

import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
METADATA_FILE = DATA_DIR / "metadata.json"
TOOLS_FILE = DATA_DIR / "tools.json"
HTML_FILE = ROOT_DIR / "index.html"


def validate_data():
    print(f"Validating {METADATA_FILE.name}...")
    if not METADATA_FILE.exists():
        raise FileNotFoundError(f"Missing {METADATA_FILE}")
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert "name" in meta, "Missing 'name' in metadata.json"
    assert "version" in meta, "Missing 'version' in metadata.json"

    print(f"Validating {TOOLS_FILE.name}...")
    if not TOOLS_FILE.exists():
        raise FileNotFoundError(f"Missing {TOOLS_FILE}")
    with open(TOOLS_FILE, "r", encoding="utf-8") as f:
        tools = json.load(f)
    assert isinstance(tools, list), "tools.json must be a JSON array"
    assert len(tools) >= 30, f"Expected at least 30 tools, found {len(tools)}"

    for t in tools:
        assert "name" in t, f"Tool missing 'name': {t}"
        assert "category" in t, f"Tool {t['name']} missing 'category'"
        assert "description" in t, f"Tool {t['name']} missing 'description'"
        assert "parameters" in t, f"Tool {t['name']} missing 'parameters'"

    print(f"Successfully validated {len(tools)} tools and metadata v{meta['version']}.")
    return meta, tools


def render_tool_html(t):
    badge_colors = {
        "Diagnostics": "bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-300",
        "Cellular": "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-300",
        "SMS": "bg-purple-100 text-purple-900 dark:bg-purple-900/40 dark:text-purple-300",
        "Wi-Fi": "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-300",
        "System": "bg-rose-100 text-rose-900 dark:bg-rose-900/40 dark:text-rose-300",
        "Tuning": "bg-teal-100 text-teal-900 dark:bg-teal-900/40 dark:text-teal-300",
    }
    badge_class = badge_colors.get(t.get("category", "Diagnostics"), "bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-300")

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


def build():
    meta, tools = validate_data()
    print("Pre-rendering tools into index.html...")

    if not HTML_FILE.exists():
        print(f"Warning: {HTML_FILE} does not exist yet. Will create.")
        return

    content = HTML_FILE.read_text(encoding="utf-8")

    grid_html = "\n".join([render_tool_html(t) for t in tools])

    start_tag = '<!-- TOOLS_GRID_START -->'
    end_tag = '<!-- TOOLS_GRID_END -->'
    if start_tag in content and end_tag in content:
        parts = content.split(start_tag)
        pre = parts[0] + start_tag + "\n"
        post = "\n        " + end_tag + parts[1].split(end_tag)[1]
        new_content = pre + grid_html + post
        HTML_FILE.write_text(new_content, encoding="utf-8")
        print(f"[✓] Successfully injected {len(tools)} pre-rendered tools into {HTML_FILE.name}")
    else:
        print("Note: TOOLS_GRID markers not found in index.html; client-side JS hydration will render dynamically.")


if __name__ == "__main__":
    build()
