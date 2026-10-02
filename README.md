<p align="center">
  <img src="https://raw.githubusercontent.com/BrunoMoreno/findmyjob/main/assets/logo.png" alt="FindMyJob logo" width="320">
</p>

# FindMyJob - Job Search Tool

[![PyPI](https://img.shields.io/pypi/v/findmyjob.svg)](https://pypi.org/project/findmyjob/)
[![Python](https://img.shields.io/pypi/pyversions/findmyjob.svg)](https://pypi.org/project/findmyjob/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/BrunoMoreno/findmyjob/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-brunomoreno.github.io-blue)](https://brunomoreno.github.io/findmyjob/)

A job search tool that uses "dorks" (advanced search queries) to find job
openings on job boards and Applicant Tracking Systems (ATS), plus **public ATS
JSON APIs** for structured data with real posting dates.

Works as a **command-line tool** and as a **Python library**.

**Full documentation: https://brunomoreno.github.io/findmyjob/**

## Features

- **Multiple search sources**: Indeed, LinkedIn, Glassdoor + ATS dork domains
  (Greenhouse, Lever, Workday, SmartRecruiters, Ashby, Workable)
- **Public ATS JSON APIs**: structured jobs (with real posting dates) from
  Greenhouse, Lever, Ashby and SmartRecruiters, one request per company
- **11 countries supported**, including Brazil, Portugal, USA, UK, Canada,
  Germany, Spain, Mexico, Argentina, Colombia and Chile
- **Brazilian boards**: Gupy, InfoJobs, Vagas.com, Catho and Programathor
  (via `-c br`)
- **Two search backends**: DuckDuckGo (default) or Google Custom Search
- **ATS discovery**: find which companies use which ATS, then monitor them
- **Keyword and date filters**, enrichment, JSON/XLSX/CSV output
- **SQLite database** with URL-normalized deduplication, ideal for cronjobs
- **Python API** for every feature

## Installation

```bash
pip install findmyjob
```

Python 3.10+ is required. See the
[installation guide](https://brunomoreno.github.io/findmyjob/installation/)
for source and development setups.

## Quickstart

```bash
# Dork search, saving to a database
findmyjob "backend engineer" -c br -l remote --db ~/findmyjob.db

# ATS JSON APIs: discover companies, then fetch their open jobs
findmyjob ats discover "backend engineer" -c br -o companies.json
findmyjob ats fetch -t companies.json --db ~/findmyjob.db

# Database utilities
findmyjob db --db ~/findmyjob.db stats
findmyjob db --db ~/findmyjob.db export --format csv -o jobs.csv
```

## Documentation

| Guide | Contents |
|-------|----------|
| [Quickstart](https://brunomoreno.github.io/findmyjob/quickstart/) | Five-minute walkthrough |
| [CLI reference](https://brunomoreno.github.io/findmyjob/cli/) | Every command and flag |
| [ATS JSON APIs](https://brunomoreno.github.io/findmyjob/ats/) | Discovery, fetch and targets format |
| [Database](https://brunomoreno.github.io/findmyjob/database/) | Deduplication, utilities, cron |
| [Data model](https://brunomoreno.github.io/findmyjob/data-model/) | JSON/CSV/XLSX/SQLite fields |
| [Python API](https://brunomoreno.github.io/findmyjob/python-api/) | Use it as a library |
| [Production](https://brunomoreno.github.io/findmyjob/production/) | Running it for a job board |
| [Troubleshooting](https://brunomoreno.github.io/findmyjob/troubleshooting/) | FAQ and common issues |

## Python API

```python
from findmyjob import search_ddg, filter_jobs, save_to_db, db_stats

jobs = search_ddg('site:boards.greenhouse.io "backend engineer"', 10, None)
jobs = filter_jobs(jobs, max_days=7, keywords=["backend"])
save_to_db(jobs, "findmyjob.db")
print(db_stats("findmyjob.db")["total"])
```

## Contributing

Contributions are welcome. See the
[contributing guide](https://brunomoreno.github.io/findmyjob/contributing/).

1. Fork the project
2. Create a branch (`git checkout -b feature/new-feature`)
3. Commit your changes
4. Push and open a Pull Request

## License

MIT. See [LICENSE](LICENSE).
