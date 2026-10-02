"""Dependency-free run summaries and metrics files.

The dict produced by :func:`run_summary` feeds both the structured log record
(``--log-json``) and the optional ``--metrics-file``, so a scheduler can read
counts and timing without parsing the database.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .console import log


def run_summary(*, started: float, **fields) -> dict:
    """Return ``fields`` plus a rounded ``duration_s`` since ``started``."""
    fields["duration_s"] = round(time.monotonic() - started, 3)
    return fields


def write_metrics(path: str | Path, summary: dict) -> None:
    """Write a metrics summary as pretty JSON."""
    Path(path).expanduser().write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def emit_run_summary(summary: dict, metrics_file: str | None = None) -> None:
    """
    Log ``summary`` as a structured record and optionally write it to a file.

    With ``--log-json`` the fields become top-level JSON keys; with the default
    formatter only the ``run summary`` message is shown. Writing the metrics
    file never aborts a run.
    """
    log.info("run summary", extra=summary)
    if metrics_file:
        try:
            write_metrics(metrics_file, summary)
        except OSError as e:
            log.error("failed to write metrics file: %s", e)
