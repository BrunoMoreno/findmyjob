# Roadmap - FindMyJob

Planning document for the next iterations. It covers the documentation
overhaul, how the library can be used in production (for job-board portals),
the gaps that block that use, and a phased execution plan.

Nothing here is a commitment: it is a working list to be trimmed as items ship.
Delivered work is recorded in [`improvements.md`](improvements.md).

---

## 1. Documentation overhaul

### 1.1 Current state

- The README is ~350 lines and mixes installation, usage, ATS, full argument
  reference, output formats, Python API, tests, examples and contributing.
- There is no API reference, no production guide, no data model, no
  architecture overview, no FAQ and no changelog. `docs/` only contains
  `improvements.md`.

### 1.2 Proposal

Adopt **MkDocs Material** (Markdown, built-in search, versionable, deploy to
GitHub Pages from a workflow) and shrink the README to a landing page that
links into the docs.

```text
docs/
  index.md            Overview and features
  installation.md
  quickstart.md       5 minutes: install, search, create the database
  cli.md              Commands, full flag table, exit codes
  ats.md              Providers, discover, fetch, companies.json format
  database.md         Schema, deduplication, purge/export
  python-api.md       Reference generated with mkdocstrings
  architecture.md     Module map and data flow
  data-model.md       JSON/CSV/XLSX/DB fields with types and examples
  production.md       Production guide (section 2)
  recipes/            cron, systemd timer, GitHub Actions, Docker
  troubleshooting.md  FAQ (rate limits, zero results, wrong slug)
  contributing.md
  changelog.md        Link to releases / Keep a Changelog
mkdocs.yml
```

Additional quality items:

- [ ] Ship a `py.typed` marker and keep type hints complete for API consumers.
- [ ] Add `examples/` with runnable scripts (ATS fetch, scheduled ingestion).
- [ ] Add a root `CHANGELOG.md` (Keep a Changelog); keep `improvements.md`
      and this roadmap separate from shipped history.
- [ ] Add issue/PR templates and `SECURITY.md`.

### 1.3 Documentation debt found

- [ ] README lists **Workday** and **Workable** among the ATS, but the JSON
      API only supports Greenhouse, Lever, Ashby and SmartRecruiters. Those two
      are dork-only domains (`config.ATS`), not providers.
- [ ] `config.ATS` uses `smartrecruiters.com` while discovery uses
      `jobs.smartrecruiters.com`; unify the domain.
- [ ] Document the `company` column as explicitly best effort.
- [ ] Document the exit codes (`0`, `1`, `2`) and the empty-run behavior.

---

## 2. Production usage (job-board portals)

`findmyjob` is an ingestion engine, not a platform. A portal typically needs:
collect -> normalize -> deduplicate -> persist -> reconcile status -> serve.

### 2.1 Architecture options

1. **CLI + SQLite as a landing zone** (lowest effort). cron/systemd runs
   `ats fetch` and/or the dork search into SQLite; an ETL reads it with
   `db export` and loads it into the portal's Postgres.
2. **Library inside a worker** (recommended). A worker (Celery / Arq / RQ /
   cron) imports `findmyjob`, orchestrates per segment/region and writes
   straight to Postgres. Blocked today by global state (see section 3).
3. **Native sink** (evolution). `findmyjob sync --dsn postgres://...` writes
   directly to the portal database with SQLAlchemy.

### 2.2 Data model for the portal

- Use **Postgres** as the source of truth; SQLite only as staging (limited
  write concurrency).
- Tables: `companies`, `job_postings` (per source), `jobs` (canonical,
  portal-facing), `targets`, `ingest_runs` (observability) and optionally
  `raw_payloads` (reprocessing).
- **Natural key** `(source, external_id)`. The ATS fetchers do not expose the
  posting id yet, which prevents idempotent upserts.
- **Deduplication**: `link_key` (normalized URL) covers tracking variants.
  Cross-source dedup (LinkedIn vs Greenhouse) needs fuzzy matching on
  `title + company + location` plus a company registry with aliases.
- **Lifecycle**: ATS APIs only return open postings, so absence means closed.
  Use `last_seen_at` plus a reconciliation step (`active` -> `stale` ->
  `closed`). No command exists for this today.
- Missing fields for a portal: `salary`, `department`, `employment_type`,
  `remote`, full description (currently truncated at 4000 chars) and HTML
  kept separately from plain text.

### 2.3 Operations and reliability

- **Concurrency** for ATS calls (sequential today) with a per-host limit,
  jittered backoff and `Retry-After` handling on `429`.
- **Caching** via ETag / Last-Modified / TTL per board to avoid re-downloading
  unchanged payloads.
- **Incremental scheduling**: per-company TTL (only check what is due) is
  essential with thousands of targets.
- **Observability**: structured (JSON) logging, metrics (new jobs, errors per
  provider, latency) and a **zero-result warning** per target (a strong signal
  of a wrong slug). Record every run.
- **Secrets**: `GOOGLE_API_KEY` / `GOOGLE_CX` via a secret manager.
- **Backfill/pagination**: SmartRecruiters paginates (fixed `limit=100` today),
  so large boards lose postings.

### 2.4 Portal integration

- Define a stable **`JobPosting` (Pydantic)** model instead of loose `dict`s,
  so the contract can be versioned.
- Emit events/webhooks for new jobs (notifications).
- Reference stack: FastAPI/Django + Postgres + worker + Redis + search
  (Postgres FTS, Meilisearch or OpenSearch).

### 2.5 Legal and ethical

- Dorking LinkedIn/Indeed/Glassdoor often violates their terms and is fragile
  (rate limits). For commercial production, prefer **ATS APIs and official
  board APIs**, and state this clearly in the docs.

---

## 3. Library gaps blocking production

| # | Gap | Impact |
|---|-----|--------|
| 1 | ATS fetchers do not return `external_id` / provider | cannot upsert idempotently |
| 2 | No data model (loose `dict`) | unstable contract for the portal |
| 3 | Global state (`console.QUIET`, `USE_COLOR`, log handlers) | hard to embed in a worker/threads |
| 4 | Sequential ATS requests | slow at scale |
| 5 | No pagination (SmartRecruiters) | missed postings on large boards |
| 6 | No Postgres sink | an extra ETL is mandatory |
| 7 | No closed-posting reconciliation | portal shows dead jobs |
| 8 | No ETag/TTL cache per board | wasted requests and blocking risk |
| 9 | Truncated description; no salary/dept/type/remote | poor data in the portal |
| 10 | No `--follow` / incremental or per-target TTL | reprocesses everything |
| 11 | Flat targets file, no metadata (region/tags/priority) | hard to go multi-tenant |

---

## 4. Phased plan

### Phase 0 - Documentation (fast, no code change)

- [ ] Set up MkDocs Material + GitHub Pages workflow.
- [ ] Split the README into the structure above; keep a short landing page.
- [ ] Write `data-model.md` (JSON/CSV/XLSX/DB fields).
- [ ] Write `production.md` (section 2).
- [ ] Fix the documentation debt in 1.3.

### Phase 1 - Production readiness

- [x] `JobPosting` Pydantic model across all fetchers.
- [x] Expose `external_id` / provider in ATS results.
- [ ] Configurable concurrency for ATS requests.
- [x] Reconciliation command (`db mark-stale`) and run records.
- [ ] Postgres sink (`sync --dsn`).
- [ ] Structured logging and metrics.

### Phase 2 - Scale

- [ ] Per-target TTL / incremental mode (`--follow`).
- [ ] ETag / Last-Modified caching per board.
- [ ] Pagination for all providers (starting with SmartRecruiters).
- [ ] Proxy/rotation and jittered backoff on `429`.

### Phase 3 - Portal features

- [ ] Company registry with aliases.
- [ ] Cross-source deduplication.
- [ ] Events/webhooks for new postings.
