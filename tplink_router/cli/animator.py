"""
Claude-Code-Inspired Terminal Motion & Transient Spinner Engine for tplink-cli.

Provides smooth, non-blocking 15 FPS animations for direct CLI subcommands:
  - Morphing Claude-style starburst glyph (✢ ✳ ✶ ✻ ✽ ✻ ✶ ✳)
  - Sweeping TP-Link Brand Cyan (#4DCCD5 -> #ECFEFF) or Monochrome B&W character shimmer
  - Live 0.1s elapsed hardware handshake timer
  - Zero-pollution transient erasure (\r\033[2K) before panel output renders
  - Automatic suppression under --json, --legacy, --no-anim, NO_COLOR, CI=true, or non-TTY pipes
"""

from contextlib import contextmanager
import os
import sys
import threading
import time
from typing import Any, Iterator, Optional, Sequence, Tuple

STARBURST_FRAMES: Tuple[str, ...] = ("✢", "✳", "✶", "✻", "✽", "✻", "✶", "✳")
BRAILLE_FRAMES: Tuple[str, ...] = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

# RGB stops from base slate -> TP-Link Cyan -> ice crest
_CYAN_WAVE: Tuple[Tuple[int, int, int], ...] = (
    (148, 163, 184),  # distance >= 4 : cool slate
    (56, 189, 248),   # distance == 3 : sky cyan
    (77, 204, 213),   # distance == 2 : official TP-Link Cyan (#4DCCD5)
    (165, 243, 252),  # distance == 1 : bright cyan
    (236, 254, 255),  # distance == 0 : luminous crest
)

_MONO_WAVE: Tuple[Tuple[int, int, int], ...] = (
    (140, 140, 148),  # distance >= 4 : muted silver
    (175, 175, 182),  # distance == 3
    (210, 210, 216),  # distance == 2
    (238, 238, 242),  # distance == 1
    (255, 255, 255),  # distance == 0 : pure white crest
)


def _rgb(r: int, g: int, b: int, bold: bool = False) -> str:
    prefix = "\033[1;" if bold else "\033["
    return f"{prefix}38;2;{r};{g};{b}m"


def shimmer_text(text: str, tick: int, mono: bool = False) -> str:
    """
    Render `text` with a Claude-Code-style sweeping luminescence wave at `tick`.
    """
    if not text:
        return ""
    if os.environ.get("NO_COLOR"):
        return text

    ramp: Sequence[Tuple[int, int, int]] = _MONO_WAVE if mono else _CYAN_WAVE
    n = len(text)
    period = max(12, n + 10)
    crest = (tick * 2) % period - 4

    out = []
    last_code = ""
    for idx, ch in enumerate(text):
        dist = abs(idx - crest)
        if dist == 0:
            r, g, b = ramp[4]
            code = _rgb(r, g, b, bold=True)
        elif dist == 1:
            r, g, b = ramp[3]
            code = _rgb(r, g, b, bold=True)
        elif dist == 2:
            r, g, b = ramp[2]
            code = _rgb(r, g, b, bold=False)
        elif dist == 3:
            r, g, b = ramp[1]
            code = _rgb(r, g, b, bold=False)
        else:
            r, g, b = ramp[0]
            code = _rgb(r, g, b, bold=False)

        if code != last_code:
            out.append(code)
            last_code = code
        out.append(ch)

    out.append("\033[0m")
    return "".join(out)


def format_spinner_frame(
    label: str,
    tick: int,
    elapsed_s: float,
    mono: bool = False,
) -> str:
    """Build a single transient Claude-Code-style spinner status line."""
    glyph = STARBURST_FRAMES[tick % len(STARBURST_FRAMES)]
    braille = BRAILLE_FRAMES[tick % len(BRAILLE_FRAMES)]
    if os.environ.get("NO_COLOR"):
        return f"  {glyph} {label} ({elapsed_s:.1f}s)"

    if mono:
        g_col = "\033[1;38;2;255;255;255m"
        muted = "\033[38;2;140;140;148m"
    else:
        g_col = "\033[1;38;2;77;204;213m"
        muted = "\033[38;2;100;116;139m"
    rst = "\033[0m"
    shimmered = shimmer_text(label, tick=tick, mono=mono)
    return f"  {g_col}{glyph}{rst} {shimmered} {muted}{braille} {elapsed_s:.1f}s{rst}"


def should_animate(args: Optional[Any] = None, stream: Optional[Any] = None) -> bool:
    """
    Determine whether transient terminal animations should run.

    Animations automatically disable when:
      - --json, --legacy, or --no-anim is active
      - NO_COLOR, CI, or TPLINK_NO_ANIM environment variable is set
      - TERM is 'dumb'
      - Output stream is not an interactive TTY (e.g. piped or StringIO captured)
    """
    if os.environ.get("NO_COLOR") or os.environ.get("TPLINK_NO_ANIM"):
        return False
    ci_val = os.environ.get("CI", "").lower()
    if ci_val in ("1", "true", "yes"):
        return False
    if os.environ.get("TERM", "").lower() == "dumb":
        return False

    if args is not None:
        if getattr(args, "json", False):
            return False
        if getattr(args, "legacy", False):
            return False
        if getattr(args, "no_anim", False):
            return False

    target = stream if stream is not None else sys.stderr
    isatty_fn = getattr(target, "isatty", None)
    if not callable(isatty_fn) or not isatty_fn():
        return False
    # Also ensure stdout isn't redirected to a non-TTY pipe when using default stderr
    if stream is None:
        out_tty = getattr(sys.stdout, "isatty", None)
        if not callable(out_tty) or not out_tty():
            return False
    return True


_ACTIVE_LOCK = threading.Lock()
_ACTIVE_SPINNER: Optional["AnimatedSpinner"] = None


def clear_active_spinner() -> None:
    """Idempotently stop and erase any currently active CLI spinner before stdout output."""
    global _ACTIVE_SPINNER
    with _ACTIVE_LOCK:
        sp = _ACTIVE_SPINNER
        _ACTIVE_SPINNER = None
    if sp is not None:
        sp.stop()


class AnimatedSpinner:
    """Thread-driven transient status bar that erases cleanly when finished."""

    def __init__(
        self,
        label: str,
        mono: bool = False,
        enabled: bool = True,
        stream: Optional[Any] = None,
        interval: float = 0.065,
    ) -> None:
        self._label = label
        self._mono = mono
        self._enabled = enabled
        self._stream = stream if stream is not None else sys.stderr
        self._interval = interval
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._start_ts = 0.0
        self._rendered = False
        self._stopped = False

    def update(self, new_label: str) -> None:
        """Update the active action message mid-flight without restarting the timer."""
        with self._lock:
            self._label = new_label

    def _loop(self) -> None:
        tick = 0
        try:
            self._stream.write("\033[?25l")
            self._stream.flush()
        except Exception:
            return

        while not self._stop_evt.is_set():
            elapsed = max(0.0, time.monotonic() - self._start_ts)
            with self._lock:
                lbl = self._label
            line = format_spinner_frame(lbl, tick=tick, elapsed_s=elapsed, mono=self._mono)
            try:
                self._stream.write(f"\r\033[2K{line}")
                self._stream.flush()
                self._rendered = True
            except Exception:
                break
            tick += 1
            self._stop_evt.wait(self._interval)

    def start(self) -> "AnimatedSpinner":
        global _ACTIVE_SPINNER
        if not self._enabled:
            return self
        clear_active_spinner()
        self._stopped = False
        self._start_ts = time.monotonic()
        self._stop_evt.clear()
        with _ACTIVE_LOCK:
            _ACTIVE_SPINNER = self
        self._thread = threading.Thread(target=self._loop, name="tplink-cli-animator", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        global _ACTIVE_SPINNER
        if not self._enabled or self._stopped:
            return
        self._stopped = True
        self._stop_evt.set()
        with _ACTIVE_LOCK:
            if _ACTIVE_SPINNER is self:
                _ACTIVE_SPINNER = None
        if self._thread is not None:
            self._thread.join(timeout=0.35)
            self._thread = None
        try:
            if self._rendered:
                self._stream.write("\r\033[2K")
            self._stream.write("\033[?25h")
            self._stream.flush()
        except Exception:
            pass

    def __enter__(self) -> "AnimatedSpinner":
        return self.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


@contextmanager
def router_spinner(
    label: str,
    args: Optional[Any] = None,
    mono: Optional[bool] = None,
    stream: Optional[Any] = None,
) -> Iterator[AnimatedSpinner]:
    """
    Context manager wrapping blocking router HTTP/RSA operations with a smooth
    Claude-Code-style starburst & sweeping shimmer indicator.
    """
    is_mono = bool(mono) if mono is not None else bool(getattr(args, "mono", False))
    enabled = should_animate(args=args, stream=stream)
    spinner = AnimatedSpinner(label=label, mono=is_mono, enabled=enabled, stream=stream)
    spinner.start()
    try:
        yield spinner
    finally:
        spinner.stop()
