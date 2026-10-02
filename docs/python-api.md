# Python API

Every feature is available as a library through the `findmyjob` package.

```python
from findmyjob import (
    # search and filtering
    search_ddg, search_google, plan_queries, filter_jobs, extract_company,
    normalize_url, parse_posted_date,
    # output
    save_json, save_csv, save_xlsx,
    # database
    init_db, save_to_db, db_stats, db_export, db_purge,
    # ATS APIs
    fetch_greenhouse, fetch_lever, fetch_ashby, fetch_smartrecruiters,
    fetch_targets, load_targets,
    # ATS discovery
    extract_ats_target, extract_ats_targets, discover_targets, save_targets,
    AtsError,
)
```

## Search

| Function | Signature |
|----------|-----------|
| `search_ddg` | `(query, max_results, country=None, retries=3, backoff=2.0) -> list[dict]` |
| `search_google` | `(query, max_results, country=None, retries=3, backoff=2.0) -> list[dict]` |
| `plan_queries` | `(role, locals_, group, country) -> list[dict]` |

`country` is a mapping from `findmyjob.config.COUNTRIES`
(`findmyjob.cli.COUNTRIES` is also available for backwards compatibility).
`search_google` reads `GOOGLE_API_KEY` and `GOOGLE_CX` from the environment and
raises `SearchError` when they are missing.

```python
from findmyjob import plan_queries, search_ddg
from findmyjob.cli import COUNTRIES

plan = plan_queries("backend engineer", ["remote"], "boards", None)  # general
for item in plan:
    for result in search_ddg(item["query"], 10, None):
        print(result["title"], result["link"])

brazil = COUNTRIES["br"]
for item in plan_queries("python developer", ["remote"], "all", brazil):
    ...
```

## Filtering and enrichment

| Function | Signature |
|----------|-----------|
| `filter_jobs` | `(jobs, min_date=None, max_date=None, keywords=None, exclude_keywords=None, max_days=0, keep_unknown_dates=True) -> list[dict]` |
| `extract_company` | `(link, title) -> str` |
| `normalize_url` | `(url) -> str` |
| `parse_posted_date` | `(value, now=None) -> datetime \| None` |

```python
from findmyjob import filter_jobs, extract_company, normalize_url

clean = filter_jobs(jobs, max_days=7, keywords=["backend"],
                    exclude_keywords=["junior"])
for job in clean:
    job["company"] = extract_company(job["link"], job["title"])
    job["link"] = normalize_url(job["link"])   # strips tracking params
```

`extract_company` is best effort and may return an empty string.

## Output

| Function | Signature |
|----------|-----------|
| `save_json` | `(path, meta, jobs) -> None` |
| `save_xlsx` | `(path, meta, jobs) -> bool` |
| `save_csv` | `(path, jobs) -> bool` |

## Database

| Function | Signature |
|----------|-----------|
| `init_db` | `(db=None) -> Path` |
| `save_to_db` | `(jobs, db=None) -> int` (new inserts) |
| `db_stats` | `(db=None) -> dict` |
| `db_export` | `(db=None, fmt="json", limit=None, since_days=None) -> str` |
| `db_purge` | `(db=None, older_than_days=None) -> int` |

## ATS APIs

| Function | Signature |
|----------|-----------|
| `fetch_greenhouse` / `fetch_lever` / `fetch_ashby` / `fetch_smartrecruiters` | `(slug, **kwargs) -> list[dict]` |
| `fetch_targets` | `(targets, *, retries=3, backoff=2.0, timeout=20.0, delay=0.0) -> (jobs, errors)` |
| `load_targets` | `(path) -> dict[str, list[str]]` |
| `extract_ats_target` | `(link) -> (provider, slug) \| None` |
| `extract_ats_targets` | `(links) -> dict[str, list[str]]` |
| `discover_targets` | `(role, country, locals_, max_results, backend="ddg", *, retries=3, delay=2.0, providers=PROVIDERS) -> (targets, errors)` |
| `save_targets` | `(path, targets, merge=False) -> dict[str, list[str]]` |

```python
from findmyjob import fetch_targets, save_to_db

targets = {"greenhouse": ["stripe"], "lever": ["spotify"]}
jobs, errors = fetch_targets(targets, retries=3, timeout=20, delay=1.0)
print(f"{len(jobs)} jobs, {len(errors)} errors")
save_to_db(jobs, "findmyjob.db")
```

A failing company does not abort the rest; check the `errors` list. Individual
fetchers raise `AtsError` on final failure.

## End-to-end example

```python
from findmyjob import (
    plan_queries, search_ddg, filter_jobs, extract_company,
    init_db, save_to_db, db_stats,
)

init_db("findmyjob.db")

jobs = []
for item in plan_queries("backend engineer", ["remote"], "boards", None):
    for result in search_ddg(item["query"], 10, None):
        jobs.append({
            "title": result["title"],
            "link": result["link"],
            "company": extract_company(result["link"], result["title"]),
        })

jobs = filter_jobs(jobs, max_days=7)
print(f"{save_to_db(jobs, 'findmyjob.db')} new jobs")
print(db_stats("findmyjob.db")["total"])
```

!!! warning "Global state"
    The CLI helpers `setup_logging` and `console.QUIET` are process-global. If
    you embed FindMyJob in a long-running service, call `setup_logging` once at
    startup (or avoid the CLI helpers entirely) and prefer the pure functions
    above.
