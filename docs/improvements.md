# Improvements - FindMyJob

Record of the improvements delivered and a list of ideas that remain open.
Historical diagnosis (the original problems) is kept at the bottom for
context; everything in the "Delivered" section is implemented, tested and
shipped.

---

## 1. Delivered

### 1.1 Data quality

- **Company extraction is now conservative.** `extract_company` still reads
  the company from ATS/job-board URLs (reliable), but the title heuristic was
  tightened: it rejects work model (`Remote`, `Hybrid`), seniority (`Pleno`,
  `Senior`) and known city/country (`São Paulo`, `Brasil`) segments, and it
  prefers the last ` - ` / `|` segment so that
  `Software Engineer - Python - Stone Pagamentos` resolves to
  `Stone Pagamentos`. The `company` column is best effort and may be empty.
- **In-run deduplication uses normalized URLs.** JSON/XLSX/CSV output and the
  SQLite layer now deduplicate by the tracking-free URL key, not by the raw
  link. Campaign variants (`utm_*`, `gh_src`, `lever-*`) collapse into one
  job.
- **`gh_jid` is preserved.** On Greenhouse-hosted boards it is the job
  identifier (`stripe.com/jobs/search?gh_jid=8172487`), so stripping it would
  merge distinct jobs.

### 1.2 Search and filtering

- **Retries respect `--quiet`.** The retry notices in `search_ddg`/`search_google`
  go through the console helper and are silenced by `-q/--quiet`.
- **Real date filtering** (`min_date`, `max_date`, `max_days`,
  `--strict-dates`) with an optional cutoff, plus Google CSE pagemap dates.
- **Brazilian boards** added to `-c br`: Gupy, InfoJobs, Vagas.com, Catho and
  Programathor.

### 1.3 ATS public JSON APIs (new)

Dork results only expose a snippet, which makes date filtering weak (specially
on the default DuckDuckGo backend). The new `ats` workflow fetches structured
data directly from the ATS, one request per company:

- Providers: **Greenhouse**, **Lever**, **Ashby**, **SmartRecruiters**.
- `findmyjob ats discover <role> [-c country] [-l term]` runs one dork per
  provider and extracts company slugs into a `companies.json` targets file
  (`--merge` to append, `--dry-run` to preview).
- `findmyjob ats fetch -t companies.json` fetches every target through the
  provider API, applies the same filters and writes the same outputs/database
  as the dork search.
- Real posting dates from the APIs make `--max-days` / `--strict-dates`
  meaningful. A failing company does not abort the run; exit code `2` means
  every target failed.

### 1.4 Internal refactor

`cli.py` is now a thin orchestrator. The logic lives in focused modules, all
re-exported from `findmyjob.cli` for backward compatibility:

| Module | Responsibility |
|--------|----------------|
| `config.py` | Boards/ATS domains, country settings |
| `console.py` | ANSI colors and logging |
| `dates.py` | Posting-date parsing and filtering |
| `dedup.py` | URL normalization |
| `enrich.py` | Company extraction |
| `search.py` | DuckDuckGo/Google backends and query planning |
| `db.py` | SQLite persistence |
| `output.py` | JSON/XLSX/CSV writers |
| `interactive.py` | Interactive prompt flow |
| `ats.py` | ATS JSON APIs |
| `discover.py` | ATS target discovery |
| `cli.py` | Argument parsing, subcommands, orchestration |

### 1.5 Tooling and docs

- Public **Python API** documented in the README and exported from
  `findmyjob/__init__.py`.
- `docs/improvements.md` refreshed to match reality.
- Test suite grown from 53 to 75 tests, covering the ATS providers,
  discovery, dedup fixes, company extraction and quiet retries.

### 1.6 Maintenance fixes

- **The database is created even when a run finds no jobs.** `save_to_db`
  returned early on an empty list, so `--db` only produced a file when there
  was something to insert. Runs that legitimately end with zero jobs — no
  results, `--filter-*`, or `--strict-dates` on the default ddg backend —
  silently left no database behind, which broke the documented cronjob.
  `init_db(path)` now creates the file and schema up front, and the CLI calls
  it whenever `--db` is passed (both the dork search and `ats fetch`).
- **`--version` / `-V`** prints the installed version for `findmyjob`,
  `findmyjob ats` and `findmyjob db`.

The test suite is now at 78 tests.

---

## 2. Open ideas

- Cache/rate-limit controls for `ats fetch` with large target lists.
- More providers (Workable, Recruitee, Personio, Teamtailor).
- Optional concurrency for the ATS requests.
- Location-normalization helpers for cross-provider filtering.
- A `--follow`/`--incremental` mode that only reports jobs not seen before.

---

## 3. Historical diagnosis (for context)

The list below is what motivated the work above; all items are fixed unless
noted in "Open ideas".

1. **Python version incompatibility** - `from __future__ import annotations`
   added and `requires-python` updated to `>=3.10`.
2. **Incomplete `filter_jobs`** - `min_date`/`max_date` implemented; the age
   filter became opt-in via `--max-days`.
3. **Discarded data / empty columns** - snippet captured as description;
   company and description are populated and persisted.
4. **Deduplication and tracking parameters** - `normalize_url` +
   `link_key` unique index; output dedup uses normalized URLs.
5. **SQLite export and tooling** - `db stats`, `db export`, `db purge`;
   `--csv`; interactive DB question.
6. **Test coverage and CI/CD** - SQLite, date, enrichment, CSV, ATS tests and
   `.github/workflows/tests.yml`.
7. **Repository maintenance** - `.gitignore` for SQLite files, `__all__`
   aligned, English docs, logo, MIT license.
