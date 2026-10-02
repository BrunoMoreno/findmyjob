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

- a **new** job is inserted and gets `first_seen_at` and `last_seen_at`;
- an **existing** job only gets `last_seen_at` (and `updated_at`) refreshed.

`save_to_db` returns the number of newly inserted jobs.

!!! note
    Greenhouse `gh_jid` is preserved because it identifies the job
    (`stripe.com/jobs/search?gh_jid=8172487`).

## Utilities

```bash
# Statistics: totals, first/last seen, per source and per day
findmyjob db --db ~/findmyjob.db stats
findmyjob db --db ~/findmyjob.db stats --json

# Export everything to JSON or CSV (stdout or file)
findmyjob db --db ~/findmyjob.db export --format csv -o jobs.csv
findmyjob db --db ~/findmyjob.db export --since-days 7 --limit 100

# Remove jobs last seen more than 30 days ago (asks for confirmation)
findmyjob db --db ~/findmyjob.db purge --older-than 30
findmyjob db --db ~/findmyjob.db purge --older-than 30 --yes
```

`db purge` uses `created_at` as the cutoff. Without `--older-than`, it removes
**all** jobs.

## Schema

The full field list is in [Data model](data-model.md#sqlite). The relevant
columns for lifecycle management are `first_seen_at` and `last_seen_at`:
`db purge --older-than N` prunes postings that have not been seen recently,
which is a simple way to age out closed positions.

## Programmatic use

```python
from findmyjob import init_db, save_to_db, db_stats, db_export, db_purge

init_db("findmyjob.db")                 # create file + schema
inserted = save_to_db(jobs, "findmyjob.db")
print(db_stats("findmyjob.db")["total"])
open("jobs.csv", "w").write(db_export("findmyjob.db", fmt="csv"))
db_purge("findmyjob.db", older_than_days=30)
```

## Production note

SQLite is perfect for a single scheduled worker. For a web application with
concurrent writers, use SQLite only as a landing zone and load it into
PostgreSQL. See the [Production guide](production.md).
