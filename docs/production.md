# Production guide

FindMyJob is an **ingestion engine**, not a platform. This guide describes how
to run it reliably behind a job-board portal: collect, normalize, deduplicate,
persist, reconcile and serve.

!!! warning "Terms of service and legality"
    Dorking LinkedIn, Indeed and Glassdoor may violate their terms of service
    and is fragile (rate limits, IP blocks). For commercial use, prefer the
    **public ATS APIs** and official board APIs, and review each source's terms
    before redistributing data.

## Architecture options

### 1. CLI + SQLite landing zone (lowest effort)

A scheduler runs the CLI into SQLite; an ETL loads it into the portal database.

```cron
0 8 * * * findmyjob ats fetch -t /etc/findmyjob/companies.json \
  --db /var/lib/findmyjob/landing.db --no-json --no-xlsx --quiet \
  --log-file /var/log/findmyjob/ingest.log
```

Then a small job reads the landings with `db export` and upserts into Postgres.

### 2. Library inside a worker (recommended)

A worker (Celery / Arq / RQ / a cron script) imports `findmyjob`, orchestrates
per segment or region and writes straight to Postgres. This gives you retries,
metrics and transactions at the right layer.

```python
from findmyjob import fetch_targets, filter_jobs, save_to_db

jobs, errors = fetch_targets(targets, retries=3, timeout=20, delay=0.5)
jobs = filter_jobs(jobs, max_days=2)
new = save_to_db(jobs, "landing.db")
# then upsert `jobs` into your Postgres schema
```

See the [global state warning](python-api.md#end-to-end-example) before
embedding the library in a long-running process.

### 3. Native sink (evolution)

A `sync --dsn postgres://...` command that writes directly into the portal
database would remove the ETL step. Track this in the roadmap.

## Data model for a portal

Keep SQLite as a **landing/staging** store and use **PostgreSQL** as the source
of truth.

Suggested tables:

| Table | Purpose |
|-------|---------|
| `companies` | Company registry with normalized name, slug and aliases |
| `job_postings` | One row per posting per source (raw-ish) |
| `jobs` | Canonical, portal-facing job |
| `targets` | Which companies to monitor, with metadata |
| `ingest_runs` | One row per run: counts, errors, duration |

### Identity and deduplication

- **Within a source**: `link_key` (normalized URL) is already unique, so
  tracking variants collapse.
- **Across sources**: the same job often appears on several boards. Match on a
  canonical identity such as `(company, title, location)`, ideally backed by a
  company registry and fuzzy matching.
- **Natural key for upserts**: `(source, external_id)`. The ATS fetchers do not
  expose the posting id yet — until they do, use `link_key`.

### Lifecycle

ATS APIs only return **open** postings, so a posting that disappears is
probably closed. Use `first_seen_at` / `last_seen_at`:

1. Every run refreshes `last_seen_at`.
2. A reconciliation step marks postings not seen in N runs as `stale`, then
   `closed`.
3. `db purge --older-than N` removes or archives them.

## Scheduling

- Prefer **incremental, per-company scheduling** over full sweeps once you have
  thousands of targets: only re-check a company when its TTL has expired.
- Run **discovery** (`ats discover`) less often than **fetch** (targets change
  slowly; postings change daily).
- Spread requests over time (`--delay`) and use retries with backoff. The
  built-in retry uses exponential backoff.

## Reliability and observability

- **Zero-result warning**: a company that returns 0 jobs is usually a wrong
  slug. Alert on it instead of silently monitoring nothing.
- **Exit codes**: `2` means every query/target failed — alert on it.
- **Structured logs**: pipe `--log-file` into your log stack; run a worker per
  source so failures are attributable.
- **Metrics** worth tracking: jobs fetched, new jobs, errors per provider,
  request latency, number of targets checked.
- **Dead-man's switch**: a successful run should ping a healthcheck; a missed
  run pages you.

## Data quality gaps

Be aware of the following when designing the portal:

- `company` is best effort and may be empty.
- Descriptions are truncated to 4000 characters; store the full HTML yourself
  if you need it.
- `salary`, `department`, `employment_type` and `remote` are not normalized
  yet.
- SmartRecruiters responses are paginated (currently a fixed `limit=100`), so
  very large boards may be incomplete.

## Scale

- ATS requests are currently sequential; add concurrency with a per-host limit.
- Cache board responses with ETag/Last-Modified to avoid re-downloading
  unchanged payloads.
- Handle `429` with `Retry-After` and jittered backoff.

These are tracked in the project roadmap (kept on the repository's `planning`
branch until the items ship).

## Reference stack

A typical deployment:

```text
scheduler/worker  --->  findmyjob (ingest)  --->  PostgreSQL
                                                   |
                                                   v
                                   FastAPI/Django app  --->  search
                                              (Postgres FTS / Meilisearch)
```

Emit an event or webhook for newly inserted jobs if you need notifications.
