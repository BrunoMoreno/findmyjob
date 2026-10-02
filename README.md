<p align="center">
  <img src="https://raw.githubusercontent.com/BrunoMoreno/findmyjob/main/assets/logo.png" alt="FindMyJob logo" width="320">
</p>

# FindMyJob - Job Search Tool

A job search tool that uses "dorks" (advanced search queries) to find job openings on job boards and Applicant Tracking Systems (ATS).

## Features

- **Multiple search sources**: Indeed, LinkedIn, Glassdoor + ATS (Greenhouse, Lever, Workday, SmartRecruiters, Ashby, Workable)
- **11 countries supported**: Brazil, Portugal, USA, UK, Canada, Germany, Spain, Mexico, Argentina, Colombia and Chile
- **Brazilian boards**: Gupy, InfoJobs, Vagas.com, Catho and Programathor (via `-c br`)
- **Two search backends**: DuckDuckGo (default) or Google Custom Search API
- **Public ATS JSON APIs**: Fetch structured jobs (with real posting dates) from Greenhouse, Lever, Ashby and SmartRecruiters, one request per company
- **ATS discovery**: Find which companies use which ATS from search results, then monitor them via API
- **Keyword filters**: Include or exclude terms from results
- **Date filtering**: Maximum age, minimum/maximum date and strict mode
- **Enrichment**: company extracted from the link/title and description from the snippet
- **JSON, XLSX and CSV output**: Formatted spreadsheet with hyperlinks and filters
- **SQLite database**: Deduplication by normalized URL, ideal for cronjobs
- **Database utilities**: `db stats`, `db export` and `db purge` subcommands
- **Python API**: Use the search, filtering, database and ATS functions as a library
- **Logging and exit codes**: `--quiet`, `--log-file` and exit code for cronjobs
- **Automatic retry**: Configurable attempts on network failure (silenced by `--quiet`)
- **Interactive mode or CLI**: Friendly interface or command-line arguments

## Installation

### Install from PyPI (recommended)

```bash
pip install findmyjob
```

### Install from source

```bash
# Install from the project directory
pip install .

# Or in development mode (changes take effect immediately)
pip install -e .
```

### Manual setup (development)

```bash
# Create a virtual environment
python -m venv env
source env/bin/activate  # Linux/Mac
# env\Scripts\activate   # Windows

# Install the dependencies
pip install -r requirements.txt
```

## Usage

After installing the package, you can use the `findmyjob` command directly.

### Interactive Mode

```bash
findmyjob
```

The script will ask about the role, country, location and search sources.

### CLI Mode (Command Line)

```bash
# General search
findmyjob "backend engineer" -l remote -l latam

# Brazil only
findmyjob "backend engineer" -c br

# Brazil + remote + ATS only
findmyjob "backend engineer" -c br -l remote --group ats

# With keyword filters
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

# Only show the queries (without running the search)
findmyjob "backend engineer" --show-queries
```

It can also be used as a Python module:

```bash
python -m findmyjob "backend engineer" -c br
```

### Database Utilities

```bash
# Database statistics
findmyjob db --db ~/findmyjob.db stats

# Export everything to JSON or CSV (stdout or file)
findmyjob db --db ~/findmyjob.db export --format csv -o jobs.csv

# Export only jobs from the last 7 days
findmyjob db --db ~/findmyjob.db export --since-days 7

# Remove jobs last seen more than 30 days ago (asks for confirmation)
findmyjob db --db ~/findmyjob.db purge --older-than 30
```

### Cronjob Usage

The command returns exit code `2` when **all** queries fail and `1`
on fatal errors — useful for monitoring. Example `crontab` entry:

```cron
# Every day at 8am: search recent jobs and store them in the database
0 8 * * * /usr/local/bin/findmyjob "backend engineer" -c br -l remote \
  --max-days 3 --strict-dates --db "$HOME/findmyjob.db" \
  --no-json --no-xlsx --quiet --log-file "$HOME/findmyjob.log"
```

### Using Google Custom Search (Optional)

```bash
export GOOGLE_API_KEY="your_key"
export GOOGLE_CX="your_cx"
findmyjob "backend engineer" -b google
```

## ATS JSON APIs

Search dorks only return a snippet, so the posting date is unreliable. The
public ATS JSON APIs return structured data (including a real posting date)
and need **one request per company** instead of one query per board — much
faster and more accurate for monitoring a fixed list of companies.

Supported providers:

| Provider | Endpoint | Company identifier |
|----------|----------|--------------------|
| Greenhouse | `boards-api.greenhouse.io` | board token (`stripe`) |
| Lever | `api.lever.co` | company slug (`spotify`) |
| Ashby | `api.ashbyhq.com` | job board name (`openai`) |
| SmartRecruiters | `api.smartrecruiters.com` | company id (`Accor`) |

### 1. Discover companies (dorks)

Run one dork per provider and collect the company slugs found in the results:

```bash
findmyjob ats discover "backend engineer" -c br -m 10 -o companies.json

# Merge with an existing file instead of overwriting it
findmyjob ats discover "python developer" -l remote --merge -o companies.json

# Preview without writing
findmyjob ats discover "golang" --dry-run
```

This writes a targets file:

```json
{
  "greenhouse": ["stripe", "nubank"],
  "lever": ["spotify"],
  "ashby": ["openai"],
  "smartrecruiters": ["Accor"]
}
```

### 2. Fetch jobs (JSON APIs)

```bash
# Fetch every target, keep jobs from the last 30 days
findmyjob ats fetch -t companies.json --db ~/findmyjob.db

# Only some providers, with keyword filters, and a CSV
findmyjob ats fetch -t companies.json --provider greenhouse --provider lever \
  --filter-exclude junior --csv -o ats_jobs

# Everything, no date cutoff
findmyjob ats fetch -t companies.json --max-days 0
```

`ats fetch` supports the same filters, output flags and database flags as the
dork search (`--filter-include`, `--filter-exclude`, `--max-days`,
`--strict-dates`, `--min-date`, `--max-date`, `--csv`, `--no-json`,
`--no-xlsx`, `--db`, `-q/--quiet`, `-o/--output`), plus `--retries`,
`--timeout` and `--delay` for the API calls. Exit code `2` means every target
failed.

The `company` column is best effort: ATS URLs are reliable, title-derived
names are not, and may be empty when no company can be identified.

## Arguments

| Argument | Description |
|----------|-------------|
| `role` | Role to search for (e.g. "backend engineer") |
| `-c, --country` | Restrict to one country (br, pt, us, uk, ca, de, es, mx, ar, co, cl) |
| `-l, --local` | Extra location/term (repeatable) |
| `-g, --group` | Source group: boards, ats, all |
| `-b, --backend` | Search backend: ddg, google |
| `-m, --max` | Results per query (default: 8) |
| `-o, --output` | Base name for output files |
| `-i, --interactive` | Force interactive mode |
| `--delay` | Seconds between queries (default: 2.0) |
| `--retries` | Attempts on error (default: 3) |
| `--show-queries` | Only print the queries |
| `--no-color` | Disable colors |
| `--list-countries` | List available countries |
| `--filter-include` | Keywords that must be in the title |
| `--filter-exclude` | Keywords that must NOT be in the title |
| `--max-days` | Maximum job age in days (0 disables; default: 3) |
| `--strict-dates` | Drop jobs without an identifiable date |
| `--min-date` | Minimum posting date (YYYY-MM-DD) |
| `--max-date` | Maximum posting date (YYYY-MM-DD) |
| `--db` | Save results to a SQLite database (e.g. findmyjob.db) |
| `--csv` | Also save a CSV file |
| `--no-json` | Do not save a JSON file |
| `--no-xlsx` | Do not save an XLSX file |
| `-q, --quiet` | Suppress progress output |
| `-v, --verbose` | Detailed logging |
| `--log-file` | Log file (append) |

## Output

The script can generate the following files (controlled by flags):

1. **`.json`**: Raw data with search metadata
2. **`.xlsx`**: Formatted spreadsheet with:
   - "Jobs" sheet: List of jobs with hyperlinks, company and description
   - "Search" sheet: Search metadata
3. **`.csv`** (optional, with `--csv`): Lightweight, dependency-free version
4. **SQLite database** (optional): Stores jobs with automatic deduplication by normalized URL — ideal for periodic cron runs.

## Python API

Every feature is available as a library through the `findmyjob` package:

```python
from findmyjob import (
    search_ddg, plan_queries, filter_jobs, extract_company, normalize_url,
    save_json, save_csv, save_xlsx, save_to_db, db_stats,
    fetch_greenhouse, fetch_targets, load_targets,
    extract_ats_targets, discover_targets,
)

# 1. Plan and run a dork search
plan = plan_queries("backend engineer", ["remote"], "boards", None)
jobs = []
for item in plan:
    for result in search_ddg(item["query"], 10, None):
        jobs.append({
            "title": result["title"],
            "link": result["link"],
            "company": extract_company(result["link"], result["title"]),
        })

# 2. Filter and persist
jobs = filter_jobs(jobs, max_days=7, keywords=["backend"])
save_json("jobs.json", {"role": "backend engineer"}, jobs)
save_to_db(jobs, "findmyjob.db")
print(db_stats("findmyjob.db")["total"])

# 3. Or fetch directly from the ATS JSON APIs
targets = {"greenhouse": ["stripe"], "lever": ["spotify"]}
ats_jobs, errors = fetch_targets(targets)
```

`load_targets(path)` reads the `companies.json` format, and
`extract_ats_targets(links)` / `discover_targets(...)` implement the discovery
half. `AtsError` is raised for a failing provider request.

## Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run the tests
pytest -v

# Lint check
ruff check .
```

## Project Structure

Files tracked in the repository:

```
findmyjob/
├── .github/
│   └── workflows/
│       ├── tests.yml          # CI: tests and lint on push/PR
│       └── publish-pypi.yml   # CI: publish to PyPI on release
├── assets/
│   └── logo.png               # Project logo
├── docs/
│   └── improvements.md        # Analysis and improvement plan
├── src/
│   └── findmyjob/
│       ├── __init__.py        # Package exports and version
│       ├── config.py          # Boards/ATS domains and country settings
│       ├── console.py         # ANSI colors and logging
│       ├── dates.py           # Posting-date parsing and filtering
│       ├── dedup.py           # URL normalization for deduplication
│       ├── enrich.py          # Best-effort company extraction
│       ├── search.py          # DuckDuckGo/Google backends and query planning
│       ├── db.py              # SQLite persistence
│       ├── output.py          # JSON/XLSX/CSV writers
│       ├── interactive.py     # Interactive prompt flow
│       ├── ats.py             # ATS JSON APIs (Greenhouse, Lever, Ashby, SR)
│       ├── discover.py        # ATS company discovery from dorks
│       ├── cli.py             # Argument parsing, subcommands and orchestration
│       └── __main__.py        # Entry point for python -m
├── tests/
│   ├── test_main.py           # Core tests
│   └── test_ats.py            # ATS APIs, discovery and data-quality tests
├── .gitignore                 # Files ignored by git
├── LICENSE                    # MIT license
├── pyproject.toml             # Package configuration (PEP 621)
├── README.md                  # Documentation
└── requirements.txt           # Pinned dependencies
```

Generated at runtime and not tracked (see [Output](#output)): the SQLite
database (`findmyjob.db`) and the `jobs_*.json`, `jobs_*.csv` and
`jobs_*.xlsx` result files. Virtual environments such as `env/` are local too.

## Usage Examples

### Search for Python jobs in Brazil

```bash
findmyjob "python developer" -c br -l remote
```

### Search for Go jobs with a filter

```bash
findmyjob "golang" --filter-include backend --filter-exclude senior
```

### Search all ATS sources

```bash
findmyjob "backend engineer" -g ats -m 10
```

## Contributing

1. Fork the project
2. Create a branch for your feature (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
