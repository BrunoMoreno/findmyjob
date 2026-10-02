"""Posting-date parsing and job filtering."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from .console import log

_RELATIVE_PATTERNS = [
    (re.compile(r"\b(\d+)\s*(?:minute|min)s?\s+ago\b", re.I), "minutes"),
    (re.compile(r"\b(\d+)\s*(?:hour|hr)s?\s+ago\b", re.I), "hours"),
    (re.compile(r"\b(\d+)\s*days?\s+ago\b", re.I), "days"),
    (re.compile(r"\b(\d+)\s*(?:week|wk)s?\s+ago\b", re.I), "weeks"),
    (re.compile(r"\b(\d+)\s*months?\s+ago\b", re.I), "months"),
    (re.compile(r"\b(\d+)\s*(?:minuto|min)s?\s+atr[áa]s\b", re.I), "minutes"),
    (re.compile(r"\b(\d+)\s*horas?\s+atr[áa]s\b", re.I), "hours"),
    (re.compile(r"\b(\d+)\s*dias?\s+atr[áa]s\b", re.I), "days"),
    (re.compile(r"\b(\d+)\s*semanas?\s+atr[áa]s\b", re.I), "weeks"),
    (re.compile(r"\b(\d+)\s*meses?\s+atr[áa]s\b", re.I), "months"),
    # Portuguese: "há 3 dias", "ha 2 horas"
    (re.compile(r"\bh[áa]\s+(\d+)\s*(?:minuto|min)s?\b", re.I), "minutes"),
    (re.compile(r"\bh[áa]\s+(\d+)\s*horas?\b", re.I), "hours"),
    (re.compile(r"\bh[áa]\s+(\d+)\s*dias?\b", re.I), "days"),
    (re.compile(r"\bh[áa]\s+(\d+)\s*semanas?\b", re.I), "weeks"),
    (re.compile(r"\bh[áa]\s+(\d+)\s*meses?\b", re.I), "months"),
]


def parse_posted_date(value, now: datetime | None = None) -> datetime | None:
    """
    Extract a posting date from common formats.

    Accepts datetime, number (days ago), ISO ("2026-09-28"), relative text
    ("2 days ago", "há 3 dias", "today", "yesterday").
    """
    if value is None:
        return None
    now = now or datetime.now()

    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # convention: number = days ago
        return now - timedelta(days=float(value))

    text = str(value).strip()
    if not text:
        return None

    low = text.lower()
    if low in ("today", "hoje"):
        return now
    if low in ("yesterday", "ontem"):
        return now - timedelta(days=1)

    for pattern, unit in _RELATIVE_PATTERNS:
        m = pattern.search(text)
        if m:
            amount = int(m.group(1))
            if unit == "minutes":
                return now - timedelta(minutes=amount)
            if unit == "hours":
                return now - timedelta(hours=amount)
            if unit == "days":
                return now - timedelta(days=amount)
            if unit == "weeks":
                return now - timedelta(weeks=amount)
            if unit == "months":
                return now - timedelta(days=30 * amount)

    # ISO / dateutil-like "YYYY-MM-DD[ HH:MM:SS]"
    candidate = text.replace("T", " ").split(".")[0]
    candidate = re.sub(r"(Z|[+-]\d{2}:?\d{2})$", "", candidate).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


def _job_posted_datetime(job: dict) -> datetime | None:
    """Return the job posting date, if identifiable."""
    for key in ("posted_at", "date", "published", "age_days"):
        value = job.get(key)
        if value is None:
            continue
        dt = parse_posted_date(value)
        if dt is not None:
            return dt
    # try to extract from snippet/body ("2 days ago")
    for key in ("snippet", "body"):
        text = job.get(key)
        if text:
            dt = parse_posted_date(text)
            if dt is not None:
                return dt
    return None


def _in_date_range(job: dict, lo: datetime | None, hi: datetime | None,
                   keep_unknown: bool) -> bool:
    """Check whether the job is in the [lo, hi) range. Without a date, follow keep_unknown."""
    posted = _job_posted_datetime(job)
    if posted is None:
        return keep_unknown
    if lo is not None and posted < lo:
        return False
    if hi is not None and posted >= hi:
        return False
    return True


def filter_jobs(jobs: list[dict], min_date: str | None = None,
                max_date: str | None = None,
                keywords: list[str] | None = None,
                exclude_keywords: list[str] | None = None,
                max_days: int = 0,
                keep_unknown_dates: bool = True) -> list[dict]:
    """
    Filter jobs by date and keywords.

    Args:
        jobs: List of jobs
        min_date: Minimum date (format: YYYY-MM-DD)
        max_date: Maximum date (format: YYYY-MM-DD)
        keywords: Keywords that must be in the title
        exclude_keywords: Keywords that must NOT be in the title
        max_days: Maximum age in days (0 disables)
        keep_unknown_dates: keep jobs without an identifiable date

    Returns:
        List of filtered jobs
    """
    filtered = jobs.copy()

    if keywords:
        filtered = [j for j in filtered
                    if any(kw.lower() in j["title"].lower() for kw in keywords)]

    if exclude_keywords:
        filtered = [j for j in filtered
                    if not any(kw.lower() in j["title"].lower() for kw in exclude_keywords)]

    if max_days and max_days > 0:
        cutoff = datetime.now() - timedelta(days=max_days)
        filtered_new = []
        for j in filtered:
            posted = _job_posted_datetime(j)
            if posted is None:
                if keep_unknown_dates:
                    filtered_new.append(j)
                continue
            if posted >= cutoff:
                filtered_new.append(j)
        filtered = filtered_new

    if min_date:
        try:
            lo = datetime.strptime(min_date, "%Y-%m-%d")
            filtered = [j for j in filtered
                        if _in_date_range(j, lo, None, keep_unknown_dates)]
        except ValueError:
            log.warning("invalid min_date (use YYYY-MM-DD): %s", min_date)

    if max_date:
        try:
            hi = datetime.strptime(max_date, "%Y-%m-%d") + timedelta(days=1)
            filtered = [j for j in filtered
                        if _in_date_range(j, None, hi, keep_unknown_dates)]
        except ValueError:
            log.warning("invalid max_date (use YYYY-MM-DD): %s", max_date)

    return filtered
