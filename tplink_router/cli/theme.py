"""
Unified Modern Terminal Theme & Box-Layout Engine for TP-Link Router CLI.

Zero third-party PyPI dependencies — uses pure Python stdlib with TrueColor
TP-Link Cyan (#4DCCD5), 256-color fallback, Monochrome B&W (--mono), and
NO_COLOR compliance. Guarantees exact column alignment for rounded Unicode
panels, tables, signal bars, gauges, and status badges.
"""

import os
import re
import shutil
import unicodedata
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@dataclass(frozen=True)
class ThemePalette:
    brand: str
    brand_bold: str
    teal: str
    white: str
    bold: str
    text: str
    muted: str
    border: str
    success: str
    warning: str
    danger: str
    inverse: str
    reset: str
    mono: bool = False
    plain: bool = False


def get_palette(mono: bool = False, plain: bool = False) -> ThemePalette:
    """Return active color palette honoring --mono and NO_COLOR."""
    if os.environ.get("NO_COLOR"):
        plain = True

    if plain:
        return ThemePalette(
            brand="",
            brand_bold="",
            teal="",
            white="",
            bold="",
            text="",
            muted="",
            border="",
            success="",
            warning="",
            danger="",
            inverse="",
            reset="",
            mono=True,
            plain=True,
        )

    if mono:
        return ThemePalette(
            brand="\033[38;2;240;244;248m",
            brand_bold="\033[1;38;2;255;255;255m",
            teal="\033[38;2;203;213;225m",
            white="\033[1;38;2;255;255;255m",
            bold="\033[1m",
            text="\033[38;2;226;232;240m",
            muted="\033[38;2;148;163;184m",
            border="\033[38;2;100;116;139m",
            success="\033[1;38;2;255;255;255m",
            warning="\033[38;2;226;232;240m",
            danger="\033[1;38;2;255;255;255m",
            inverse="\033[7m",
            reset="\033[0m",
            mono=True,
            plain=False,
        )

    # Official TP-Link Brand Cyan (#4DCCD5) + Modern Slate/Emerald/Amber/Rose
    return ThemePalette(
        brand="\033[38;2;77;204;213m",
        brand_bold="\033[1;38;2;77;204;213m",
        teal="\033[38;2;0;164;153m",
        white="\033[1;38;2;248;250;252m",
        bold="\033[1m",
        text="\033[38;2;226;232;240m",
        muted="\033[38;2;148;163;184m",
        border="\033[38;2;71;85;105m",
        success="\033[1;38;2;16;185;129m",
        warning="\033[1;38;2;245;158;11m",
        danger="\033[1;38;2;239;68;68m",
        inverse="\033[7m",
        reset="\033[0m",
        mono=False,
        plain=False,
    )


def strip_ansi(text: str) -> str:
    """Remove all ANSI CSI sequences from a string."""
    return ANSI_ESCAPE_RE.sub("", text)


def _char_display_width(ch: str) -> int:
    if not ch or ch in ("\ufe0f", "\ufe0e", "\u200d"):
        return 0
    cat = unicodedata.category(ch)
    if cat.startswith("M") or cat == "Cc":
        return 0
    eaw = unicodedata.east_asian_width(ch)
    if eaw in ("W", "F"):
        return 2
    return 1


def visible_len(text: str) -> int:
    """Compute exact terminal column width of an ANSI-formatted string."""
    clean = strip_ansi(text)
    return sum(_char_display_width(c) for c in clean)


def truncate_ansi(text: str, max_width: int, ellipsis: str = "…") -> str:
    """Truncate an ANSI-styled string to fit within max_width visible columns."""
    if max_width <= 0:
        return ""
    if visible_len(text) <= max_width:
        return text

    target = max(0, max_width - visible_len(ellipsis))
    out: List[str] = []
    cur_w = 0
    idx = 0
    has_ansi = False

    while idx < len(text):
        m = ANSI_ESCAPE_RE.match(text, idx)
        if m:
            out.append(m.group(0))
            has_ansi = True
            idx = m.end()
            continue
        ch = text[idx]
        cw = _char_display_width(ch)
        if cur_w + cw > target:
            break
        out.append(ch)
        cur_w += cw
        idx += 1

    res = "".join(out) + ellipsis
    if has_ansi:
        res += "\033[0m"
    return res


def pad_right(text: str, width: int) -> str:
    """Pad or truncate ANSI string to exact visible width."""
    vlen = visible_len(text)
    if vlen > width:
        text = truncate_ansi(text, width)
        vlen = visible_len(text)
    return text + (" " * max(0, width - vlen))


def wrap_ansi(text: str, max_width: int) -> List[str]:
    """Wrap long lines cleanly within max_width columns."""
    if max_width <= 4 or visible_len(text) <= max_width:
        return [text]
    # If line contains ANSI styling, preserve prefix indent on wrapped plain chunks
    clean = strip_ansi(text)
    words = clean.split(" ")
    lines: List[str] = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip() if cur else w
        if visible_len(cand) <= max_width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            while visible_len(w) > max_width:
                lines.append(w[:max_width])
                w = w[max_width:]
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def get_ui_width(default: int = 76, min_w: int = 58, max_w: int = 92) -> int:
    """Determine optimal responsive card width for the current terminal."""
    try:
        cols, _ = shutil.get_terminal_size((default, 24))
        return max(min_w, min(cols - 2, max_w))
    except Exception:
        return default


def status_badge(
    enabled: bool,
    on_text: str = "ENABLED",
    off_text: str = "DISABLED",
    mono: bool = False,
    warn_off: bool = False,
) -> str:
    """Format a semantic status badge with ● / ○ indicator."""
    p = get_palette(mono=mono)
    if enabled:
        if p.mono:
            return f"{p.white}[● {on_text}]{p.reset}"
        return f"{p.success}● {on_text}{p.reset}"
    if p.mono:
        return f"{p.muted}[○ {off_text}]{p.reset}"
    col = p.warning if warn_off else p.muted
    return f"{col}○ {off_text}{p.reset}"


def rating_badge(rating: str, mono: bool = False) -> str:
    """Colorize RF signal quality rating strings (Excellent, Good, Fair, Poor)."""
    p = get_palette(mono=mono)
    r_low = (rating or "").lower()
    if p.mono:
        return f"{p.bold}{rating}{p.reset}"
    if any(k in r_low for k in ("excellent", "optimal", "passed")):
        return f"{p.success}{rating}{p.reset}"
    if "good" in r_low:
        return f"{p.brand_bold}{rating}{p.reset}"
    if "fair" in r_low:
        return f"{p.warning}{rating}{p.reset}"
    return f"{p.danger}{rating}{p.reset}"


def signal_bars(bars: int, max_bars: int = 4, mono: bool = False) -> str:
    """Render Unicode RF step-bars (▂▄▆█) with active/inactive contrast."""
    p = get_palette(mono=mono)
    glyphs = ["▂", "▄", "▆", "█"]
    clamped = max(0, min(int(bars or 0), max_bars))
    active_col = p.white if p.mono else (p.success if clamped >= 3 else (p.warning if clamped == 2 else p.danger))
    parts: List[str] = []
    for i in range(max_bars):
        g = glyphs[i] if i < len(glyphs) else "█"
        if i < clamped:
            parts.append(f"{active_col}{g}{p.reset}")
        else:
            parts.append(f"{p.muted}▁{p.reset}")
    return "".join(parts) + f" {p.bold}{clamped}/{max_bars}{p.reset}"


def progress_meter(
    value: float,
    max_value: float = 100.0,
    width: int = 18,
    mono: bool = False,
    invert_danger: bool = False,
) -> str:
    """Render a smooth horizontal meter (━━━━━━━━──────)."""
    p = get_palette(mono=mono)
    ratio = 0.0 if max_value <= 0 else max(0.0, min(1.0, float(value) / float(max_value)))
    filled = int(round(ratio * width))
    empty = width - filled

    if p.mono:
        col = p.white
    elif invert_danger:
        col = p.danger if ratio >= 0.9 else (p.warning if ratio >= 0.75 else p.brand)
    else:
        col = p.success if ratio >= 0.7 else (p.brand if ratio >= 0.4 else p.warning)

    bar = f"{col}{'━' * filled}{p.reset}{p.border}{'─' * empty}{p.reset}"
    return f"{bar} {p.muted}{int(round(ratio * 100))}%{p.reset}"


def render_kv_rows(
    pairs: Sequence[Tuple[str, Any]],
    key_width: Optional[int] = None,
    mono: bool = False,
) -> List[str]:
    """Format aligned Key │ Value rows for inside a themed panel."""
    p = get_palette(mono=mono)
    if not pairs:
        return []
    kw = key_width or max(min(22, max(visible_len(str(k)) for k, _ in pairs)), 14)
    lines: List[str] = []
    for k, v in pairs:
        k_padded = pad_right(str(k), kw)
        lines.append(f"{p.muted}{k_padded}{p.reset} {p.border}│{p.reset} {p.text}{v}{p.reset}")
    return lines


def render_table_lines(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    mono: bool = False,
    max_width: int = 72,
) -> List[str]:
    """Format an ANSI-safe columnar table with header divider."""
    p = get_palette(mono=mono)
    if not headers:
        return []

    ncols = len(headers)
    str_rows = [[str(cell) for cell in r] for r in rows]
    col_widths = [visible_len(h) for h in headers]
    for r in str_rows:
        for i in range(min(ncols, len(r))):
            col_widths[i] = max(col_widths[i], visible_len(r[i]))

    gap = 2
    total_w = sum(col_widths) + gap * (ncols - 1)
    if total_w > max_width and ncols > 1:
        # Proportionally shrink widest columns first
        excess = total_w - max_width
        while excess > 0:
            widest_idx = max(range(ncols), key=lambda idx: col_widths[idx])
            if col_widths[widest_idx] <= 6:
                break
            col_widths[widest_idx] -= 1
            excess -= 1

    hdr_cells = [
        f"{p.brand_bold}{pad_right(headers[i], col_widths[i])}{p.reset}"
        for i in range(ncols)
    ]
    sep_cells = [f"{p.border}{'─' * col_widths[i]}{p.reset}" for i in range(ncols)]
    lines = [
        (" " * gap).join(hdr_cells),
        (" " * gap).join(sep_cells),
    ]

    if not str_rows:
        lines.append(f"{p.muted}(No entries){p.reset}")
        return lines

    for r in str_rows:
        row_cells: List[str] = []
        for i in range(ncols):
            val = r[i] if i < len(r) else ""
            row_cells.append(f"{p.text}{pad_right(val, col_widths[i])}{p.reset}")
        lines.append((" " * gap).join(row_cells))

    return lines


def render_section_header(title: str, mono: bool = False) -> str:
    """Sub-section title line inside a multi-section panel."""
    p = get_palette(mono=mono)
    return f"{p.brand_bold}▸ {title}{p.reset}"


def render_panel(
    title: str,
    sections: Sequence[Sequence[str]],
    subtitle: Optional[str] = None,
    footer: Optional[str] = None,
    accent: str = "brand",
    mono: bool = False,
    width: Optional[int] = None,
) -> str:
    """
    Render a rounded Unicode panel (╭───╮ ... ╰───╯) with exact column borders.

    Args:
        title: Primary uppercase/bold title on top border.
        sections: List of line-lists; multiple sections are separated by ├────┤.
        subtitle: Optional right-aligned tag on top border (e.g. 'Archer MR200').
        footer: Optional hint text embedded on bottom border or footer row.
        accent: 'brand' (Cyan), 'success' (Emerald), 'warning' (Amber), 'danger' (Rose).
        mono: Render in high-contrast Black & White monochrome.
        width: Total outer box width (defaults to responsive terminal width).
    """
    p = get_palette(mono=mono)
    box_w = width or get_ui_width()
    inner_w = max(30, box_w - 4)  # "│ " + content(inner_w) + " │"

    accent_map = {
        "brand": (p.brand_bold, p.border),
        "success": (p.success, p.border if p.mono else "\033[38;2;16;185;129m"),
        "warning": (p.warning, p.border if p.mono else "\033[38;2;245;158;11m"),
        "danger": (p.danger, p.border if p.mono else "\033[38;2;239;68;68m"),
    }
    title_col, bdr_col = accent_map.get(accent, (p.brand_bold, p.border))
    if p.plain:
        bdr_col = ""

    icon = {"brand": "◆", "success": "✔", "warning": "▲", "danger": "✖"}.get(accent, "◆")
    left_label = f" {icon} {title} "
    right_label = f" {subtitle} " if subtitle else ""

    max_title_space = box_w - 4
    if visible_len(left_label) + visible_len(right_label) + 2 > max_title_space:
        right_label = ""
    if visible_len(left_label) > max_title_space:
        left_label = truncate_ansi(left_label, max_title_space)

    dashes_top = max(1, (box_w - 2) - visible_len(left_label) - visible_len(right_label) - 1)
    top_line = (
        f"{bdr_col}╭─{p.reset}"
        f"{title_col}{left_label}{p.reset}"
        f"{bdr_col}{'─' * dashes_top}{p.reset}"
        f"{p.muted}{right_label}{p.reset}"
        f"{bdr_col}╮{p.reset}"
    )

    out_lines: List[str] = [top_line]
    non_empty_sections = [sec for sec in sections if sec is not None]

    for s_idx, sec in enumerate(non_empty_sections):
        if s_idx > 0:
            out_lines.append(f"{bdr_col}├{'─' * (box_w - 2)}┤{p.reset}")
        for raw_line in sec:
            # Handle multi-line strings safely
            for sub in str(raw_line).split("\n"):
                if visible_len(sub) > inner_w and not ANSI_ESCAPE_RE.search(sub):
                    wrapped = wrap_ansi(sub, inner_w)
                else:
                    wrapped = [truncate_ansi(sub, inner_w)]
                for wl in wrapped:
                    padded = pad_right(wl, inner_w)
                    out_lines.append(f"{bdr_col}│{p.reset} {padded} {bdr_col}│{p.reset}")

    if footer:
        foot_txt = f" {footer} "
        if visible_len(foot_txt) > box_w - 6:
            foot_txt = truncate_ansi(foot_txt, box_w - 6) + " "
        dashes_bot = max(1, (box_w - 2) - visible_len(foot_txt) - 1)
        bot_line = (
            f"{bdr_col}╰─{p.reset}"
            f"{p.muted}{foot_txt}{p.reset}"
            f"{bdr_col}{'─' * dashes_bot}╯{p.reset}"
        )
    else:
        tag = " tp-link cli "
        dashes_bot = max(1, (box_w - 2) - len(tag) - 1)
        bot_line = (
            f"{bdr_col}╰{'─' * dashes_bot}{p.reset}"
            f"{p.muted}{tag}{p.reset}"
            f"{bdr_col}─╯{p.reset}"
        )

    out_lines.append(bot_line)
    return "\n".join(out_lines)


def print_panel(
    title: str,
    sections: Sequence[Sequence[str]],
    subtitle: Optional[str] = None,
    footer: Optional[str] = None,
    accent: str = "brand",
    mono: bool = False,
    width: Optional[int] = None,
) -> None:
    """Print a themed rounded panel with vertical breathing space."""
    print()
    print(
        render_panel(
            title=title,
            sections=sections,
            subtitle=subtitle,
            footer=footer,
            accent=accent,
            mono=mono,
            width=width,
        )
    )
    print()


def print_toast(
    kind: str,
    title: str,
    detail: Optional[str] = None,
    mono: bool = False,
) -> None:
    """
    Print a sleek themed status banner for action feedback ('success', 'warning', 'danger', 'info').
    """
    accent = {
        "success": "success",
        "warning": "warning",
        "danger": "danger",
        "error": "danger",
        "info": "brand",
    }.get(kind, "brand")
    p = get_palette(mono=mono)
    col = {
        "success": p.success,
        "warning": p.warning,
        "danger": p.danger,
        "brand": p.brand_bold,
    }[accent]
    sym = {"success": "✓", "warning": "▲", "danger": "✖", "brand": "◆"}[accent]

    rows = [f"{col}{sym} {title}{p.reset}"]
    if detail:
        for dline in detail.split("\n"):
            rows.append(f"{p.muted}  {dline}{p.reset}")

    print_panel(
        title="TP-LINK ROUTER ACTION",
        sections=[rows],
        accent=accent,
        mono=mono,
    )
