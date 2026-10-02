# CLI reference

After installing the package, the `findmyjob` command is available. Running it
without arguments starts the interactive mode; passing a role runs a direct
search.

```bash
python -m findmyjob "backend engineer" -c br   # also works as a module
```

## Interactive mode

```bash
findmyjob
```

The script asks for the role, country, location, search sources and whether to
save to a database and/or generate files. `-i/--interactive` forces it even
when a role is given.

## Direct mode

```bash
# General search
findmyjob "backend engineer" -l remote -l latam

# Brazil only
findmyjob "backend engineer" -c br

# Brazil + remote, ATS sources only
findmyjob "backend engineer" -c br -l remote --group ats

# Keyword filters
findmyjob "backend engineer" --filter-include senior --filter-exclude junior

# Save to a SQLite database (ideal for cronjobs)
findmyjob "python developer" -c br --db ~/findmyjob.db

# Save only to the database, no files
findmyjob "golang" --db findmyjob.db --no-json --no-xlsx

# Also generate a CSV file
findmyjob "golang" --csv

# Only jobs posted in the last 3 days (drops those without a date)
findmyjob "backend engineer" -c br --max-days 3 --strict-dates

# Filter by date range
findmyjob "backend engineer" --min-date 2026-09-01 --max-date 2026-10-01

# Quiet mode + log to file (good for cron)
findmyjob "backend engineer" --db ~/findmyjob.db --quiet --log-file ~/findmyjob.log

# List available countries
findmyjob --list-countries

# Only show the queries, without running the search
findmyjob "backend engineer" --show-queries

# Show the installed version
findmyjob --version
```

## Search backends

The default backend is **DuckDuckGo** (`-b ddg`) and needs no credentials. The
**Google Custom Search** backend (`-b google`) requires two environment
variables:

```bash
export GOOGLE_API_KEY="your_key"
export GOOGLE_CX="your_cx"
findmyjob "backend engineer" -b google
```

Google CSE also exposes posting dates through the result pagemap, so date
filtering tends to be more reliable than with DuckDuckGo.

## Output

The search can write up to four artifacts, controlled by flags:

| Artifact | Flag | Notes |
|----------|------|-------|
| JSON | default, disable with `--no-json` | Raw data with search metadata |
| XLSX | default, disable with `--no-xlsx` | Jobs + Search sheets, hyperlinks, filters |
| CSV | `--csv` | Lightweight, dependency-free |
| SQLite | `--db PATH` | Deduplicated by normalized URL |

See [Data model](data-model.md) for the exact fields.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Fatal error (e.g. invalid arguments, target file missing) |
| `2` | Every query/target failed |

Codes `1` and `2` make the tool easy to monitor from a scheduler.

## Cronjob usage

```cron
# Every day at 8am: search recent jobs and store them in the database
0 8 * * * /usr/local/bin/findmyjob "backend engineer" -c br -l remote \
  --max-days 3 --strict-dates --db "$HOME/findmyjob.db" \
  --no-json --no-xlsx --quiet --log-file "$HOME/findmyjob.log"
```

!!! tip
    The database file is created whenever `--db` is passed, even if the run
    finds no new jobs. See [Database](database.md#the-database-is-always-created).

## Argument reference

| Argument | Description |
|----------|-------------|
| `role` | Role to search for (e.g. `"backend engineer"`) |
| `-c, --country` | Restrict to one country (`br`, `pt`, `us`, `uk`, `ca`, `de`, `es`, `mx`, `ar`, `co`, `cl`) |
| `-l, --local` | Extra location/term (repeatable) |
| `-g, --group` | Source group: `boards`, `ats`, `all` |
| `-b, --backend` | Search backend: `ddg`, `google` |
| `-m, --max` | Results per query (default: 8) |
| `-o, --output` | Base name for output files |
| `-i, --interactive` | Force interactive mode |
| `--delay` | Seconds between queries (default: 2.0) |
| `--retries` | Attempts on error (default: 3) |
| `--show-queries` | Only print the queries |
| `-V, --version` | Show the installed version |
| `--no-color` | Disable colors |
| `--list-countries` | List available countries |
| `--filter-include` | Keywords that must be in the title |
| `--filter-exclude` | Keywords that must NOT be in the title |
| `--max-days` | Maximum job age in days (0 disables; default: 3) |
| `--strict-dates` | Drop jobs without an identifiable date |
| `--min-date` | Minimum posting date (`YYYY-MM-DD`) |
| `--max-date` | Maximum posting date (`YYYY-MM-DD`) |
| `--db` | Save results to a SQLite database (e.g. `findmyjob.db`) |
| `--csv` | Also save a CSV file |
| `--no-json` | Do not save a JSON file |
| `--no-xlsx` | Do not save an XLSX file |
| `-q, --quiet` | Suppress progress output |
| `-v, --verbose` | Detailed logging |
| `--log-file` | Log file (append) |

!!! note "Workday and Workable"
    Workday (`myworkdayjobs.com`) and Workable (`apply.workable.com`) are
    searchable as **dork domains** through `-g ats` / `-g all`, but the public
    ATS JSON API integration only supports Greenhouse, Lever, Ashby and
    SmartRecruiters. See [ATS JSON APIs](ats.md).
