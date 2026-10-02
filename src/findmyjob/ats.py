"""
Public ATS JSON APIs.

These endpoints give structured data (including a real posting date), unlike
search-engine snippets. One request per company, so this scales much better
than dorking ``site:boards.greenhouse.io`` for every company by hand.

Providers:
    greenhouse       boards-api.greenhouse.io/v1/boards/{token}/jobs
    lever            api.lever.co/v0/postings/{company}?mode=json
    ashby            api.ashbyhq.com/posting-api/job-board/{board}
    smartrecruiters  api.smartrecruiters.com/v1/companies/{id}/postings
"""

from __future__ import annotations

import html
import json
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

from . import console
from .models import JobPosting

PROVIDERS = ("greenhouse", "lever", "ashby", "smartrecruiters")

PROVIDER_DOMAINS = {
    "greenhouse": "boards.greenhouse.io",
    "lever": "jobs.lever.co",
    "ashby": "jobs.ashbyhq.com",
    "smartrecruiters": "jobs.smartrecruiters.com",
}

_HEADERS = {"User-Agent": "findmyjob (+https://github.com/BrunoMoreno/findmyjob)"}
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_MAX_DESCRIPTION = 4000

# One print lock keeps progress and retry output readable when several
# companies are fetched in parallel.
_PRINT_LOCK = threading.Lock()


def _emit(message: str) -> None:
    """Print a line atomically, unless --quiet was requested."""
    if console.QUIET:
        return
    with _PRINT_LOCK:
        print(message)


class AtsError(Exception):
    """Error fetching from an ATS API."""


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = _TAG_RE.sub(" ", value)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def _clean_description(value: str | None) -> str:
    text = _strip_html(value)
    if len(text) > _MAX_DESCRIPTION:
        text = text[:_MAX_DESCRIPTION].rstrip() + "..."
    return text


def _pretty_slug(slug: str) -> str:
    from .enrich import _pretty_company

    return _pretty_company(slug) or slug


def _http_json(url: str, params: dict | None = None, *, retries: int = 3,
               backoff: float = 2.0, timeout: float = 20.0):
    """GET a JSON document with retries. Raises AtsError on final failure."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            last_error = e
            if attempt < retries - 1:
                wait = backoff * (2 ** attempt)
                _emit(console.paint(
                    f"      [retry {attempt + 1}/{retries}] {e}. "
                    f"Retrying in {wait:.1f}s...", "yellow"))
                time.sleep(wait)
    raise AtsError(f"{last_error}")


def _base_job(provider: str, slug: str, *, title: str, link: str,
              location: str = "", posted_at: str | None = None,
              description: str = "", external_id: str | None = None) -> dict:
    domain = PROVIDER_DOMAINS.get(provider, provider)
    description = _clean_description(description)
    return JobPosting(
        title=title,
        link=link,
        company=_pretty_slug(slug),
        location=location,
        posted_at=posted_at,
        description=description,
        snippet=description,
        domain=domain,
        source=provider,
        query=f"ats:{provider}/{slug}",
        provider=provider,
        external_id=external_id,
    ).to_dict()


def _ms_to_iso(value) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return None


def fetch_greenhouse(slug: str, **kwargs) -> list[dict]:
    data = _http_json(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        params={"content": "true"}, **kwargs)
    jobs = []
    for item in data.get("jobs", []) if isinstance(data, dict) else []:
        location = (item.get("location") or {}).get("name", "")
        jobs.append(_base_job(
            "greenhouse", slug,
            title=item.get("title", ""),
            link=item.get("absolute_url", ""),
            location=location,
            posted_at=item.get("first_published") or item.get("updated_at"),
            description=item.get("content", ""),
            external_id=item.get("id"),
        ))
    return jobs


def fetch_lever(slug: str, **kwargs) -> list[dict]:
    data = _http_json(
        f"https://api.lever.co/v0/postings/{slug}",
        params={"mode": "json"}, **kwargs)
    jobs = []
    for item in data if isinstance(data, list) else []:
        categories = item.get("categories") or {}
        description = (item.get("descriptionPlain")
                       or item.get("description")
                       or "")
        jobs.append(_base_job(
            "lever", slug,
            title=item.get("text", ""),
            link=item.get("hostedUrl") or item.get("applyUrl", ""),
            location=categories.get("location", ""),
            posted_at=_ms_to_iso(item.get("createdAt")),
            description=description,
            external_id=item.get("id"),
        ))
    return jobs


def fetch_ashby(slug: str, **kwargs) -> list[dict]:
    data = _http_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}", **kwargs)
    jobs = []
    for item in data.get("jobs", []) if isinstance(data, dict) else []:
        if item.get("isListed") is False:
            continue
        jobs.append(_base_job(
            "ashby", slug,
            title=item.get("title", ""),
            link=item.get("jobUrl") or item.get("applyUrl", ""),
            location=item.get("location", ""),
            posted_at=item.get("publishedAt"),
            description=item.get("descriptionHtml") or item.get("descriptionPlain", ""),
            external_id=item.get("id"),
        ))
    return jobs


def fetch_smartrecruiters(slug: str, limit: int = 100, **kwargs) -> list[dict]:
    data = _http_json(
        f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
        params={"limit": limit}, **kwargs)
    jobs = []
    for item in data.get("content", []) if isinstance(data, dict) else []:
        loc = item.get("location") or {}
        location = ", ".join(
            p for p in (loc.get("city"), loc.get("region"), loc.get("country")) if p)
        posting_id = item.get("id", "")
        ref = item.get("ref") or ""
        if ref.startswith("http") and "api.smartrecruiters.com" not in ref:
            link = ref
        else:
            link = f"https://jobs.smartrecruiters.com/{slug}/{posting_id}"
        jobs.append(_base_job(
            "smartrecruiters", slug,
            title=item.get("name", ""),
            link=link,
            location=location,
            posted_at=item.get("releasedDate"),
            description=item.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", "")
            if isinstance(item.get("jobAd"), dict) else "",
            external_id=posting_id,
        ))
    return jobs


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
}


def load_targets(path: str | Path) -> dict[str, list[str]]:
    """
    Load a target-company list.

    Accepts either a mapping of provider -> list of slugs::

        {"greenhouse": ["stripe"], "lever": ["spotify"]}

    or a flat list of ``"provider/slug"`` strings::

        ["greenhouse/stripe", "lever/spotify"]
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    targets: dict[str, list[str]] = {}

    if isinstance(raw, dict):
        for provider, slugs in raw.items():
            provider = provider.lower().strip()
            if provider not in PROVIDERS:
                raise ValueError(f"unknown ATS provider: {provider!r}")
            if isinstance(slugs, str):
                slugs = [slugs]
            for slug in slugs:
                slug = str(slug).strip()
                if slug:
                    targets.setdefault(provider, []).append(slug)
    elif isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, str) or "/" not in entry:
                raise ValueError(f"invalid target entry: {entry!r} (expected 'provider/slug')")
            provider, slug = entry.split("/", 1)
            provider = provider.lower().strip()
            if provider not in PROVIDERS:
                raise ValueError(f"unknown ATS provider: {provider!r}")
            targets.setdefault(provider, []).append(slug.strip())
    else:
        raise ValueError("targets file must be an object or a list")

    return targets


class _RateLimiter:
    """Space request starts by at least ``delay`` seconds (process-wide)."""

    def __init__(self, delay: float) -> None:
        self._delay = max(0.0, delay or 0.0)
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        if not self._delay:
            return
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self._delay


def _fetch_sequential(tasks, errors: list[str], *, retries: int,
                      backoff: float, timeout: float, delay: float) -> list[dict]:
    jobs: list[dict] = []
    for provider, slug, fetcher in tasks:
        _emit(console.paint(f"== {provider}/{slug}", "bold", "cyan"))
        try:
            found = fetcher(slug, retries=retries, backoff=backoff, timeout=timeout)
        except AtsError as e:
            errors.append(f"{provider}/{slug}: {e}")
            _emit(console.paint(f"   [error] {e}", "red"))
            continue
        _emit(f"   {len(found)} job(s)")
        jobs.extend(found)
        if delay:
            time.sleep(delay)
    return jobs


def _fetch_concurrent(tasks, errors: list[str], *, retries: int,
                      backoff: float, timeout: float, delay: float,
                      concurrency: int, per_host: int) -> list[dict]:
    workers = max(1, concurrency)
    host_limit = max(1, per_host or workers)
    semaphores: dict[str, threading.Semaphore] = {}
    sem_lock = threading.Lock()
    limiter = _RateLimiter(delay)
    results: list[list[dict] | None] = [None] * len(tasks)

    def _host_semaphore(host: str) -> threading.Semaphore:
        with sem_lock:
            sem = semaphores.get(host)
            if sem is None:
                sem = threading.Semaphore(host_limit)
                semaphores[host] = sem
            return sem

    def _work(index: int, provider: str, slug: str, fetcher):
        with _host_semaphore(PROVIDER_DOMAINS.get(provider, provider)):
            limiter.wait()
            found = fetcher(slug, retries=retries, backoff=backoff, timeout=timeout)
        return index, found

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_work, index, provider, slug, fetcher):
                (index, provider, slug)
            for index, (provider, slug, fetcher) in enumerate(tasks)
        }
        for future in as_completed(futures):
            index, provider, slug = futures[future]
            try:
                _, found = future.result()
            except AtsError as e:
                errors.append(f"{provider}/{slug}: {e}")
                _emit(console.paint(f"   [error] {provider}/{slug}: {e}", "red"))
                continue
            results[index] = found
            _emit(console.paint(f"== {provider}/{slug}", "bold", "cyan")
                  + f" {len(found)} job(s)")

    jobs: list[dict] = []
    for found in results:
        if found:
            jobs.extend(found)
    return jobs


def fetch_targets(targets: dict[str, list[str]], *, retries: int = 3,
                  backoff: float = 2.0, timeout: float = 20.0,
                  delay: float = 0.0, concurrency: int = 1,
                  per_host: int = 5) -> tuple[list[dict], list[str]]:
    """
    Fetch jobs for every ``provider -> slug`` target.

    Returns ``(jobs, errors)``; a failing company does not abort the rest.

    ``concurrency > 1`` fetches several companies in parallel through a thread
    pool, with at most ``per_host`` simultaneous requests per ATS host. In that
    mode ``delay`` spaces request starts through a shared rate limiter instead
    of sleeping after each target. The default (``concurrency=1``) keeps the
    original sequential behavior.
    """
    tasks: list[tuple[str, str, Callable[..., list[dict]]]] = []
    errors: list[str] = []
    for provider, slugs in targets.items():
        fetcher = FETCHERS.get(provider)
        if fetcher is None:
            errors.append(f"{provider}: unknown provider")
            continue
        for slug in slugs:
            tasks.append((provider, slug, fetcher))

    if not tasks:
        return [], errors

    if concurrency and concurrency > 1:
        jobs = _fetch_concurrent(
            tasks, errors, retries=retries, backoff=backoff, timeout=timeout,
            delay=delay, concurrency=concurrency, per_host=per_host)
    else:
        jobs = _fetch_sequential(
            tasks, errors, retries=retries, backoff=backoff, timeout=timeout,
            delay=delay)
    return jobs, errors
