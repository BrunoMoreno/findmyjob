# Database

The SQLite database is the most useful output for periodic runs: it deduplicates
jobs so you can keep appending without worrying about duplicates.

```bash
findmyjob "python developer" -c br --db ~/findmyjob.db
```

Pass `--db` together with `--no-json --no-xlsx` to write **only** to the
database.

## The database is always created

The CLI calls `init_db()` whenever `--db` is passed, before inserting anything.
The file and schema therefore exist even when a run finds **no** new jobs —
which happens with `--strict-dates` on the DuckDuckGo backend, with keyword
filters, or when every query fails. This makes cronjobs predictable.

## Deduplication

Jobs are deduplicated by `link_key`, a normalized version of the URL with
tracking parameters removed (`utm_*`, `gh_src`, `lever-*`). That means campaign
variants of the same posting collapse into a single row.

On every run:

- a **new** job is inserted with status `active`, plus `first_seen_at` and
  `last_seen_at`;
- an **existing** job gets `last_seen_at` (and `updated_at`) refreshed, and one
  that had been marked `stale`/`closed` is reactivated.

`save_to_db` returns the number of newly inserted jobs.

!!! note
    Greenhouse `gh_jid` is preserved because it identifies the job
    (`stripe.com/jobs/search?gh_jid=8172487`).

## Lifecycle: active, stale, closed

Every job has a `status`:

| Status | Meaning |
|--------|---------|
| `active` | Seen in a recent run (the default). |
| `stale` | Was active but has not been seen for a while. |
| `closed` | Was stale and stayed away long enough. |

Because the ATS APIs only return **open** postings, a posting that disappears
is probably closed. Reconciliation is a two-step, time-based process:

```bash
# Active jobs last seen more than 30 days ago -> stale
findmyjob db --db ~/findmyjob.db mark-stale --older-than 30

# Restrict to one provider/source (optional)
findmyjob db --db ~/findmyjob.db mark-stale --older-than 30 --source greenhouse

# Jobs that have been stale for a further 7 days -> closed
findmyjob db --db ~/findmyjob.db mark-closed --older-than 7
```

The cutoff for `mark-stale` is `last_seen_at`; for `mark-closed` it is when the
job became stale. If a posting reappears in a later run it returns to `active`
automatically. Both commands ask for confirmation unless `-y/--yes` is given.

## Run records

Each run that writes to the database appends a row to the `runs` table: kind
(`search` or `ats`), scope, targets, fetched, inserted, errors, status
(`ok`/`partial`/`failed`) and timestamps.

```bash
findmyjob db --db ~/findmyjob.db runs
findmyjob db --db ~/findmyjob.db runs --limit 5 --json
```

Persist runs even when nothing is found, which makes them a simple
observability log for cron.

## Utilities

```bash
# Statistics: totals, first/last seen, per source, per status and per day
findmyjob db --db ~/findmyjob.db stats
findmyjob db --db ~/findmyjob.db stats --json

# Export everything to JSON or CSV (stdout or file)
findmyjob db --db ~/findmyjob.db export --format csv -o jobs.csv
findmyjob db --db ~/findmyjob.db export --since-days 7 --limit 100
findmyjob db --db ~/findmyjob.db export --status active

# Remove jobs last seen more than 30 days ago (asks for confirmation)
findmyjob db --db ~/findmyjob.db purge --older-than 30
findmyjob db --db ~/findmyjob.db purge --older-than 30 --yes
```

`db purge` uses `created_at` as the cutoff. Without `--older-than`, it removes
**all** jobs.

## Schema

The full field list is in [Data model](data-model.md#sqlite). The lifecycle
columns are `status` (`active`/`stale`/`closed`), `status_changed_at`,
`first_seen_at` and `last_seen_at`. Reconciliation updates `status`; `db purge
--older-than N` removes the rows themselves. There is also a `runs` table with
one row per ingest run.

## Programmatic use

```python
from findmyjob import (
    init_db, save_to_db, db_stats, db_export, db_purge,
    record_run, db_runs, mark_stale, mark_closed,
)

init_db("findmyjob.db")                 # create file + schema
inserted = save_to_db(jobs, "findmyjob.db")
record_run("findmyjob.db", "ats", fetched=len(jobs), inserted=inserted)
mark_stale("findmyjob.db", older_than_days=30)      # active -> stale
mark_closed("findmyjob.db", older_than_days=7)      # stale  -> closed
print(db_runs("findmyjob.db")[0]["status"])
db_purge("findmyjob.db", older_than_days=30)
```

## Production note

SQLite is perfect for a single scheduled worker. For a web application with
concurrent writers, use SQLite only as a landing zone and load it into
PostgreSQL. See the [Production guide](production.md).
