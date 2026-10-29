"""
Authentic TP-Link Brand Logo Renderer for Terminal UI (TUI) & CLI.

Uses Unicode Half-Block Sub-Pixel Geometry (▀, ▄, █) to render the official
TP-Link circular P-loop + detached T-corner emblem and lowercase 'tp-link'
wordmark with 1:1 square sub-pixel fidelity.

Supports:
  - Official TP-Link Cyan (#4DCCD5 / RGB 77, 204, 213) + Crisp White (#F8FAFC)
  - High-Contrast Monochrome / Black & White mode (--mono / NO_COLOR / TUI [m] key)
  - Multiple responsive variants: 'full' (62x10), 'compact' (16x8), 'mini' (12x6)
"""

import os
from typing import List


def _supports_truecolor() -> bool:
    ct = os.environ.get("COLORTERM", "").lower()
    term = os.environ.get("TERM", "").lower()
    if ct in ("truecolor", "24bit"):
        return True
    if any(k in term for k in ("xterm-256color", "kitty", "alacritty", "wezterm", "tmux", "screen-256color", "ghostty")):
        return True
    return True


def _build_full_grid() -> List[str]:
    """Constructs the 64x20 sub-pixel matrix (renders as 64 cols x 10 terminal lines)."""
    width = 64
    rows = [["."] * width for _ in range(20)]

    emblem = [
        ".........CCCCCC......",  # 00
        ".......CCCCCCCCCC....",  # 01
        "......CCCCCCCCCCCC...",  # 02
        ".....CCCCCCCCCCCCCC..",  # 03
        ".....CCCCCC..CCCCCC..",  # 04
        ".....CCCCC....CCCCC..",  # 05
        ".....CCCCC.....CCCCC.",  # 06
        ".....CCCCC.....CCCCC.",  # 07
        ".....CCCCC.....CCCCC.",  # 08
        "...............CCCCC.",  # 09
        "CCCCCCCCCC..CCCCCCCC.",  # 10
        "CCCCCCCCCC..CCCCCCCC.",  # 11
        "CCCCCCCCCC..CCCCCCC..",  # 12
        "CCCCCCCCCC..CCCCCC...",  # 13
        ".CCCCCCCCC..CCCC.....",  # 14
        ".....CCCCC...........",  # 15
        ".....CCCCC...........",  # 16
        ".....CCCCC...........",  # 17
        ".....CCCCC...........",  # 18
        "......CCC............",  # 19
    ]
    for y, r in enumerate(emblem):
        for x, ch in enumerate(r):
            rows[y][x] = ch

    def put(x0: int, y0: int, pat: List[str]) -> None:
        for dy, line in enumerate(pat):
            for dx, ch in enumerate(line):
                if ch != ".":
                    rows[y0 + dy][x0 + dx] = ch

    # 't' (cols 24..28)
    put(24, 7, [
        ".WW..",
        ".WW..",
        "WWWWW",
        ".WW..",
        ".WW..",
        ".WW..",
        ".WW..",
        ".WWWW",
    ])

    # 'p' (cols 30..36)
    put(30, 9, [
        "WWWWW..",
        "WW...WW",
        "WW...WW",
        "WW...WW",
        "WW...WW",
        "WWWWW..",
        "WW.....",
        "WW.....",
        "WW.....",
    ])

    # '-' (cols 38..40)
    put(38, 11, [
        "WWW",
        "WWW",
    ])

    # 'l' (cols 42..43)
    put(42, 6, ["WW"] * 9)

    # 'i' (cols 46..47)
    put(46, 6, ["WW", "WW", "..", "WW", "WW", "WW", "WW", "WW", "WW"])

    # 'n' (cols 50..55)
    put(50, 9, [
        "WWWWW.",
        "WW..WW",
        "WW..WW",
        "WW..WW",
        "WW..WW",
        "WW..WW",
    ])

    # 'k' (cols 57..63)
    put(57, 6, [
        "WW.....",
        "WW.....",
        "WW.....",
        "WW...WW",
        "WW..WW.",
        "WWWW...",
        "WWWW...",
        "WW..WW.",
        "WW...WW",
    ])

    return ["".join(r) for r in rows]


FULL_LOGO_GRID: List[str] = _build_full_grid()

COMPACT_EMBLEM_GRID: List[str] = [
    "......CCCCCC....",  # 00
    "....CCCCCCCCCC..",  # 01
    "...CCCCCCCCCCCC.",  # 02
    "...CCCC....CCCC.",  # 03
    "...CCCC.....CCCC",  # 04
    "...CCCC.....CCCC",  # 05
    "...CCCC.....CCCC",  # 06
    "............CCCC",  # 07
    "CCCCCCC..CCCCCCC",  # 08
    "CCCCCCC..CCCCCC.",  # 09
    "CCCCCCC..CCCCC..",  # 10
    ".CCCCCC..CCC....",  # 11
    "...CCCC.........",  # 12
    "...CCCC.........",  # 13
    "...CCCC.........",  # 14
    "....CC..........",  # 15
]

MINI_EMBLEM_GRID: List[str] = [
    "....CCCCC...",  # 00
    "...CCCCCCC..",  # 01
    "..CCC...CCC.",  # 02
    "..CCC....CCC",  # 03
    "..CCC....CCC",  # 04
    ".........CCC",  # 05
    "CCCCC.CCCCCC",  # 06
    "CCCCC.CCCCC.",  # 07
    "CCCCC.CCC...",  # 08
    "..CCC.......",  # 09
    "..CCC.......",  # 10
    "..CCC.......",  # 11
]


def get_logo_width(variant: str = "full") -> int:
    """Return exact visible character width of the requested logo variant."""
    if variant == "compact":
        return len(COMPACT_EMBLEM_GRID[0])
    if variant == "mini":
        return len(MINI_EMBLEM_GRID[0])
    return len(FULL_LOGO_GRID[0])


def render_logo_lines(variant: str = "full", mono: bool = False, plain: bool = False) -> List[str]:
    """
    Render the TP-Link half-block pixel logo into a list of terminal lines.

    Args:
        variant: 'full' (62x10 emblem + tp-link), 'compact' (16x8 emblem), or 'mini' (12x6 emblem).
        mono: Render in high-contrast Black & White monochrome instead of TP-Link Cyan.
        plain: Strip all ANSI escape sequences (used when NO_COLOR=1).
    """
    if os.environ.get("NO_COLOR"):
        plain = True

    if variant == "compact":
        grid = COMPACT_EMBLEM_GRID
    elif variant == "mini":
        grid = MINI_EMBLEM_GRID
    else:
        grid = FULL_LOGO_GRID

    if plain:
        fg_c = ""
        fg_w = ""
        bg_c = ""
        bg_w = ""
        rst = ""
    elif mono:
        if _supports_truecolor():
            fg_c = "\033[38;2;235;240;245m"
            bg_c = "\033[48;2;235;240;245m"
            fg_w = "\033[1;38;2;255;255;255m"
            bg_w = "\033[48;2;255;255;255m"
        else:
            fg_c = "\033[37m"
            bg_c = "\033[47m"
            fg_w = "\033[1;97m"
            bg_w = "\033[107m"
        rst = "\033[0m"
    else:
        if _supports_truecolor():
            # Official TP-Link Brand Cyan (#4DCCD5) + Pure Crisp White (#F8FAFC)
            fg_c = "\033[38;2;77;204;213m"
            bg_c = "\033[48;2;77;204;213m"
            fg_w = "\033[38;2;248;250;252m"
            bg_w = "\033[48;2;248;250;252m"
        else:
            fg_c = "\033[38;5;80m"
            bg_c = "\033[48;5;80m"
            fg_w = "\033[1;97m"
            bg_w = "\033[107m"
        rst = "\033[0m"

    lines: List[str] = []
    for y in range(0, len(grid), 2):
        r1 = grid[y]
        r2 = grid[y + 1]
        out_chars: List[str] = []
        for x in range(len(r1)):
            t = r1[x]
            b = r2[x]
            if t == "." and b == ".":
                out_chars.append(" ")
            elif t == b:
                col = fg_c if t == "C" else fg_w
                out_chars.append(f"{col}█{rst}")
            elif t != "." and b == ".":
                col = fg_c if t == "C" else fg_w
                out_chars.append(f"{col}▀{rst}")
            elif t == "." and b != ".":
                col = fg_c if b == "C" else fg_w
                out_chars.append(f"{col}▄{rst}")
            else:
                ft = fg_c if t == "C" else fg_w
                bb = bg_c if b == "C" else bg_w
                out_chars.append(f"{ft}{bb}▀{rst}")
        lines.append("".join(out_chars))
    return lines


def render_logo(variant: str = "full", mono: bool = False, plain: bool = False) -> str:
    """Return newline-joined TP-Link logo string."""
    return "\n".join(render_logo_lines(variant=variant, mono=mono, plain=plain))
