"""Terminal output helpers: ANSI colors and logging."""

from __future__ import annotations

import logging
import os
import sys

# ------------------------------------------------------------------- colors --
# Raw ANSI, no dependencies. Turns itself off when stdout is not a terminal
# (e.g. redirected to a file), when NO_COLOR is set, or with --no-color.
_CODES = {"bold": "1", "dim": "2", "underline": "4", "red": "31",
          "green": "32", "yellow": "33", "blue": "34", "magenta": "35", "cyan": "36"}
USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
if os.name == "nt":
    os.system("")  # enable ANSI on Windows terminals


def paint(text: str, *styles: str) -> str:
    """Wrap ``text`` in ANSI codes for the given styles, if colors are on."""
    if not USE_COLOR or not styles:
        return text
    return "\033[" + ";".join(_CODES[x] for x in styles) + "m" + text + "\033[0m"


# ------------------------------------------------------------------ logging --

log = logging.getLogger("findmyjob")
QUIET = False


def setup_logging(log_file: str | None = None, quiet: bool = False,
                  verbose: bool = False) -> None:
    """Configure logging to stdout/stderr and, optionally, to a file."""
    global QUIET
    QUIET = quiet
    level = logging.DEBUG if verbose else logging.INFO
    log.setLevel(level)
    log.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    stream.setLevel(logging.WARNING if quiet else level)
    log.addHandler(stream)

    if log_file:
        fileh = logging.FileHandler(log_file, encoding="utf-8")
        fileh.setFormatter(fmt)
        fileh.setLevel(level)
        log.addHandler(fileh)

    log.propagate = False


def is_quiet() -> bool:
    """Whether progress output should be suppressed (``--quiet``)."""
    return QUIET
