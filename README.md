<p align="center">
  <img src="https://raw.githubusercontent.com/BrunoMoreno/findmyjob/main/assets/logo.png" alt="FindMyJob logo" width="320">
</p>

# FindMyJob - Job Search Tool

A job search tool that uses "dorks" (advanced search queries) to find job openings on job boards and Applicant Tracking Systems (ATS).

## Features

- **Multiple search sources**: Indeed, LinkedIn, Glassdoor + ATS (Greenhouse, Lever, Workday, SmartRecruiters, Ashby, Workable)
- **11 countries supported**: Brazil, Portugal, USA, UK, Canada, Germany, Spain, Mexico, Argentina, Colombia and Chile
- **Two search backends**: DuckDuckGo (default) or Google Custom Search API
- **Keyword filters**: Include or exclude terms from results
- **Date filtering**: Maximum age, minimum/maximum date and strict mode
- **Enrichment**: company extracted from the link/title and description from the snippet
- **JSON, XLSX and CSV output**: Formatted spreadsheet with hyperlinks and filters
- **SQLite database**: Deduplication by normalized URL, ideal for cronjobs
- **Database utilities**: `db stats`, `db export` and `db purge` subcommands
- **Logging and exit codes**: `--quiet`, `--log-file` and exit code for cronjobs
- **Automatic retry**: Configurable attempts on network failure
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

```
findmyjob/
├── .github/
│   └── workflows/
│       ├── tests.yml          # CI: tests and lint on push/PR
│       └── publish-pypi.yml   # CI: publish to PyPI on release
├── assets/
│   └── logo.png               # Project logo
├── src/
│   └── findmyjob/
│       ├── __init__.py        # Package exports
│       ├── cli.py             # Core logic + CLI
│       └── __main__.py        # Entry point for python -m
├── tests/
│   └── test_main.py           # Automated tests
├── pyproject.toml             # Package configuration (PEP 621)
├── requirements.txt           # Dependencies
├── README.md                  # Documentation
├── LICENSE                    # MIT license
├── .gitignore                 # Files ignored by git
├── env/                       # Virtual environment (optional)
├── findmyjob.db               # SQLite database (generated with --db)
├── jobs_*.json                # JSON results
├── jobs_*.csv                 # CSV results (with --csv)
└── jobs_*.xlsx                # Excel results
```

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
