"""
Python Launcher for the Bundled vadimdemedes/ink (React + Yoga Flexbox) TUI.

Spawns Node.js running `tui.mjs` connected to `bridge.py` via serialized NDJSON
stdio, with automatic fallback to `interactive_tui.py` when Node.js is absent
or `--python-tui` is explicitly passed.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Optional, Tuple


def get_ink_bundle_path() -> Path:
    return Path(__file__).resolve().parent / "tui.mjs"


def is_ink_available() -> bool:
    """Return True if Node.js (>=18) and the bundled `tui.mjs` exist."""
    bundle = get_ink_bundle_path()
    if not bundle.is_file():
        return False
    node_bin = shutil.which("node")
    if not node_bin:
        return False
    return True


def launch_ink_tui(
    target_host: str = "http://192.168.1.1",
    mono: bool = False,
    no_anim: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Launch the full-screen vadimdemedes/ink React TUI in the active TTY.

    Returns:
        (handled, handoff_command):
          - handled: True if Ink TUI ran, False if caller should fall back to Python TUI.
          - handoff_command: Optional CLI command (e.g. 'repl') to run after TUI exits.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False, None

    node_bin = shutil.which("node")
    bundle = get_ink_bundle_path()
    if not node_bin or not bundle.is_file():
        return False, None

    # Resolve package-relative bridge module (works for both tplink_router and tplink_cli)
    cli_pkg = __name__.rsplit(".", 1)[0]
    bridge_module = f"{cli_pkg}.bridge"
    pkg_root = str(Path(__file__).resolve().parents[3])

    fd, handoff_path = tempfile.mkstemp(prefix="tplink_ink_handoff_", suffix=".txt")
    os.close(fd)

    cmd = [
        node_bin,
        str(bundle),
        "--host",
        target_host,
        "--python",
        sys.executable or "python3",
        "--bridge-module",
        bridge_module,
        "--handoff-file",
        handoff_path,
    ]
    if mono:
        cmd.append("--mono")
    if no_anim:
        cmd.append("--no-anim")

    env = dict(os.environ)
    existing_py_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{pkg_root}:{existing_py_path}" if existing_py_path else pkg_root
    if not mono and not env.get("NO_COLOR"):
        env.setdefault("FORCE_COLOR", "3")

    try:
        proc = subprocess.run(cmd, env=env)
        handoff_cmd: Optional[str] = None
        if os.path.exists(handoff_path):
            content = Path(handoff_path).read_text(encoding="utf-8").strip()
            if content:
                handoff_cmd = content
        if proc.returncode != 0 and handoff_cmd is None:
            return False, None
        return True, handoff_cmd
    except OSError:
        return False, None
    finally:
        try:
            if os.path.exists(handoff_path):
                os.remove(handoff_path)
        except OSError:
            pass
