# Architecture

FindMyJob started as a single `cli.py` and is now split into focused modules.
`cli.py` is a thin orchestrator and re-exports the public API so
`from findmyjob.cli import ...` keeps working.

## Modules

| Module | Responsibility |
|--------|----------------|
| `config.py` | Boards/ATS domains and per-country settings |
| `console.py` | ANSI colors and logging (`log`, `paint`, `setup_logging`) |
| `dates.py` | Posting-date parsing and filtering (`filter_jobs`) |
| `dedup.py` | URL normalization (`normalize_url`) |
| `enrich.py` | Company extraction (`extract_company`) |
| `search.py` | DuckDuckGo/Google backends and query planning |
| `db.py` | SQLite persistence and utilities |
| `output.py` | JSON/XLSX/CSV writers |
| `interactive.py` | Interactive prompt flow |
| `ats.py` | Public ATS JSON APIs |
| `discover.py` | ATS target discovery |
| `cli.py` | Argument parsing, subcommands, orchestration |

## Data flow

### Dork search

```text
role + country + locations
        |
        v
   plan_queries()            search.py
        |
        v
  search_ddg()/search_google()
        |
        v
  normalize_url() dedup      dedup.py
        |
        v
  filter_jobs()              dates.py
        |
        +--> save_json / save_xlsx / save_csv   output.py
        |
        +--> init_db / save_to_db               db.py
```

### ATS JSON APIs

```text
discover_targets()  -->  companies.json  -->  load_targets()
   (dorks)                (targets)              |
                                                 v
                                          fetch_targets()
                                                 |
                        +------------------------+------------------+
                        v                        v                  v
                 Greenhouse/Lever          Ashby        SmartRecruiters
                        |
                        v
              filter_jobs() -> outputs / save_to_db
```

## Design notes

- **No mandatory dependencies at import time beyond the core three**
  (`ddgs`, `requests`, `openpyxl`). `openpyxl` is imported lazily inside
  `save_xlsx`, so XLSX is optional at runtime.
- **Deduplication happens twice**: in-run (by normalized URL, for the file
  outputs) and in the database (unique `link_key` index).
- **Failures are isolated**: one failing query or one failing ATS company does
  not abort the run; errors are counted and influence the exit code.
