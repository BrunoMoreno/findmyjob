"""Search backends (DuckDuckGo, Google CSE) and query planning."""

from __future__ import annotations

import os
import time

import requests

from . import console


class SearchError(Exception):
    """Error during the search."""
    pass


def _retry_notice(attempt: int, retries: int, error: Exception, wait: float) -> None:
    """Print a retry notice unless --quiet was requested."""
    if console.QUIET:
        return
    print(console.paint(
        f"   [retry {attempt + 1}/{retries}] error: {error}. "
        f"Retrying in {wait:.1f}s...", "yellow"))


def search_ddg(query: str, max_results: int, country: dict | None,
               retries: int = 3, backoff: float = 2.0) -> list[dict]:
    """Search DuckDuckGo with automatic retry."""
    try:
        from ddgs import DDGS
    except ImportError as e:
        raise SearchError("ddgs is not installed. Run: pip install ddgs") from e

    kwargs = {"max_results": max_results}
    if country:
        kwargs["region"] = country["region"]

    last_error = None
    for attempt in range(retries):
        try:
            results = DDGS().text(query, **kwargs)
            return [{"title": r.get("title", ""), "link": r.get("href", ""),
                     "snippet": r.get("body", "")}
                    for r in results]
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                wait = backoff * (2 ** attempt)
                _retry_notice(attempt, retries, e, wait)
                time.sleep(wait)

    raise SearchError(f"Failed after {retries} attempts: {last_error}")


def search_google(query: str, max_results: int, country: dict | None,
                  retries: int = 3, backoff: float = 2.0) -> list[dict]:
    """Search Google Custom Search with automatic retry."""
    key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CX")
    if not key or not cx:
        raise SearchError("GOOGLE_API_KEY and GOOGLE_CX must be set to use the google backend")

    params = {"key": key, "cx": cx, "q": query, "num": min(max_results, 10)}
    if country:
        params["gl"] = country["gl"]

    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get("https://www.googleapis.com/customsearch/v1",
                                params=params, timeout=15)
            resp.raise_for_status()
            return [{"title": i.get("title", ""), "link": i.get("link", ""),
                     "snippet": i.get("snippet", ""),
                     "posted_at": _google_posted_date(i)}
                    for i in resp.json().get("items", [])]
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < retries - 1:
                wait = backoff * (2 ** attempt)
                _retry_notice(attempt, retries, e, wait)
                time.sleep(wait)

    raise SearchError(f"Failed after {retries} attempts: {last_error}")


def _google_posted_date(item: dict) -> str | None:
    """Try to extract the posting date from the Google CSE pagemap."""
    metatags = (item.get("pagemap") or {}).get("metatags") or []
    keys = ("article:published_time", "datepublished", "date", "og:updated_time",
            "article:modified_time", "pubdate")
    for mt in metatags:
        for k in keys:
            if k in mt and mt[k]:
                return mt[k]
    return None


BACKENDS = {"ddg": search_ddg, "google": search_google}


# ----------------------------------------------------------------- queries --

def country_term(country: dict) -> str:
    names = [f'"{n}"' for n in country["names"]]
    return names[0] if len(names) == 1 else "(" + " OR ".join(names) + ")"


def domains_for(group: str, country: dict | None) -> list[str]:
    from .config import GROUPS

    domains = list(GROUPS[group])
    if not country:
        return domains
    out = []
    for d in domains:
        if d == "indeed.com":
            d = country["indeed"]
        elif d == "glassdoor.com":
            d = country.get("glassdoor", "glassdoor.com")
        out.append(d)
    if group in ("boards", "all"):
        out += country["extra"]
    return out


def plan_queries(role: str, locals_: list[str], group: str,
                 country: dict | None) -> list[dict]:
    """Return [{domain, location, query}]."""
    plan = []
    for d in domains_for(group, country):
        if country:
            for r in (locals_ or [None]):
                terms = [country_term(country)] + ([f'"{r}"'] if r else [])
                label = country["names"][0] + (f" / {r}" if r else "")
                plan.append({"domain": d, "location": label,
                             "query": f'site:{d} "{role}" ' + " ".join(terms)})
        else:
            for loc in (locals_ or ["remote"]):
                plan.append({"domain": d, "location": loc,
                             "query": f'site:{d} "{role}" "{loc}"'})
    return plan
