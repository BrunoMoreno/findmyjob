# Quickstart

This is the shortest path from zero to a database full of jobs.

## 1. Install

```bash
pip install findmyjob
```

## 2. Run a search

Interactive mode asks for everything:

```bash
findmyjob
```

Or pass the role directly:

```bash
findmyjob "backend engineer" -c br -l remote
```

You will get a summary in the terminal and, by default, a `.json` and an
`.xlsx` file in the current directory.

## 3. Save to a database

```bash
findmyjob "python developer" -c br --db ~/findmyjob.db --no-json --no-xlsx
```

The database deduplicates by normalized URL, so running the same command twice
does not create duplicates. Existing jobs only get their `last_seen_at`
updated. See [Database](database.md).

## 4. Inspect the database

```bash
findmyjob db --db ~/findmyjob.db stats
findmyjob db --db ~/findmyjob.db export --format csv -o jobs.csv
```

## 5. Try the ATS APIs

Dork results only expose a snippet, which makes dates unreliable. The ATS
JSON APIs return structured data instead:

```bash
# Find companies that use a supported ATS
findmyjob ats discover "backend engineer" -c br -o companies.json

# Fetch their open jobs
findmyjob ats fetch -t companies.json --db ~/findmyjob.db
```

See [ATS JSON APIs](ats.md).

## Next steps

- [CLI reference](cli.md) for every flag.
- [Cronjob recipe](cli.md#cronjob-usage) to keep the database fresh.
- [Production guide](production.md) to run this for a job board.
