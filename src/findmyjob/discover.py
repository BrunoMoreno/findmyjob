"""
Discover ATS target companies from search results.

The dork half of the ATS workflow: search for ``site:jobs.lever.co "role"`` to
find which companies use which ATS, then feed those slugs into :mod:`findmyjob.ats`
to monitor them via their JSON API.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import console
from .ats import PROVIDERS

# URL shape -> (provider, slug) for the supported ATS.
ATS_URL_PATTERNS = {
    "greenhouse": re.compile(r"(?:boards|job-boards)\.greenhouse\.io/([^/?#]+)", re.I),
    "lever": re.compile(r"jobs\.lever\.co/([^/?#]+)", re.I),
    "ashby": re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)", re.I),
    "smartrecruiters": re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([^/?#]+)", re.I),
}

# Domain used in the ``site:`` dork for each provider.
ATS_DORK_DOMAINS = {
    "greenhouse": "boards.greenhouse.io",
    "lever": "jobs.lever.co",
    "ashby": "jobs.ashbyhq.com",
    "smartrecruiters": "jobs.smartrecruiters.com",
}

# Slugs that are not companies (URL sections, tracking, locale codes).
_SLUG_BLOCKLIST = {
    "search", "jobs", "job", "apply", "embed", "job-board", "postings",
    "signup", "login", "about", "api", "static", "assets",
}


def extract_ats_target(link: str) -> tuple[str, str] | None:
    """Return ``(provider, slug)`` when the link points at a supported ATS."""
    if not link:
        return None
    for provider, pattern in ATS_URL_PATTERNS.items():
        m = pattern.search(link)
        if m:
            slug = m.group(1).strip().lower()
            if slug and slug not in _SLUG_BLOCKLIST:
                return provider, slug
    return None


def extract_ats_targets(links) -> dict[str, list[str]]:
    """Group many links into ``provider -> sorted unique slugs``."""
    found: dict[str, set[str]] = {p: set() for p in PROVIDERS}
    for link in links:
        parsed = extract_ats_target(link)
        if parsed:
            provider, slug = parsed
            found[provider].add(slug)
    return {p: sorted(slugs) for p, slugs in found.items() if slugs}


def discover_targets(role: str, country: dict | None, locals_: list[str],
                     max_results: int, backend: str = "ddg", *, retries: int = 3,
                     delay: float = 2.0,
                     providers: tuple[str, ...] = PROVIDERS) -> tuple[dict[str, list[str]], list[str]]:
    """
    Run one dork per ATS provider and extract company slugs from the results.

    Returns ``(targets, errors)`` where ``targets`` is ``provider -> slugs``.
    """
    from .search import BACKENDS, SearchError, country_term

    search = BACKENDS[backend]
    found: dict[str, set[str]] = {p: set() for p in providers}
    errors: list[str] = []

    for provider in providers:
        domain = ATS_DORK_DOMAINS[provider]
        terms = []
        if country:
            terms.append(country_term(country))
        for loc in locals_ or []:
            terms.append(f'"{loc}"')
        query = f'site:{domain} "{role}"' + (" " + " ".join(terms) if terms else "")
        if not console.QUIET:
            print(console.paint(f"== {provider}", "bold", "cyan"), console.paint(query, "dim"))
        try:
            results = search(query, max_results, country, retries=retries)
        except SearchError as e:
            errors.append(f"{provider}: {e}")
            if not console.QUIET:
                print(console.paint(f"   [error] {e}", "red"))
            continue
        for result in results:
            parsed = extract_ats_target(result.get("link", ""))
            if parsed and parsed[0] == provider:
                found[provider].add(parsed[1])
        if not console.QUIET:
            print(f"   {len(found[provider])} new target(s)")
        time.sleep(delay)

    return {p: sorted(slugs) for p, slugs in found.items() if slugs}, errors


def save_targets(path: str | Path, targets: dict[str, list[str]],
                 merge: bool = False) -> dict[str, list[str]]:
    """
    Write targets to JSON, optionally merging with the existing file.
    Returns the merged mapping that was written.
    """
    path = Path(path)
    if merge and path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
        if isinstance(existing, dict):
            merged: dict[str, list[str]] = {}
            for provider in set(existing) | set(targets):
                merged[provider] = sorted(
                    set(existing.get(provider, [])) | set(targets.get(provider, [])))
            targets = merged

    path.write_text(json.dumps(targets, ensure_ascii=False, indent=2), encoding="utf-8")
    return targets
