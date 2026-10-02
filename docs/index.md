# FindMyJob

[![PyPI](https://img.shields.io/pypi/v/findmyjob.svg)](https://pypi.org/project/findmyjob/)
[![Python](https://img.shields.io/pypi/pyversions/findmyjob.svg)](https://pypi.org/project/findmyjob/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/BrunoMoreno/findmyjob/blob/main/LICENSE)

FindMyJob is a job search tool that uses **dorks** (advanced search queries) to
find job openings on job boards and Applicant Tracking Systems (ATS), plus
**public ATS JSON APIs** for structured data with real posting dates.

It works both as a command-line tool and as a Python library.

## Features

- **Multiple search sources**: Indeed, LinkedIn, Glassdoor + ATS dork domains
  (Greenhouse, Lever, Workday, SmartRecruiters, Ashby, Workable).
- **Public ATS JSON APIs**: fetch structured jobs (with real posting dates)
  from Greenhouse, Lever, Ashby and SmartRecruiters, one request per company.
- **11 countries supported**: Brazil, Portugal, USA, UK, Canada, Germany,
  Spain, Mexico, Argentina, Colombia and Chile.
- **Brazilian boards**: Gupy, InfoJobs, Vagas.com, Catho and Programathor
  (via `-c br`).
- **Two search backends**: DuckDuckGo (default) or Google Custom Search.
- **ATS discovery**: find which companies use which ATS from search results,
  then monitor them via their API.
- **Keyword and date filters**: include/exclude terms, maximum age,
  minimum/maximum date and strict mode.
- **Enrichment**: company extracted from the link/title, description from the
  snippet.
- **JSON, XLSX and CSV output**, plus a **SQLite database** with
  deduplication by normalized URL.
- **Database utilities**: `db stats`, `db export` and `db purge`.
- **Python API**: use the search, filtering, database and ATS functions as a
  library.
- **Logging and exit codes** for cronjobs: `--quiet`, `--log-file` and a
  meaningful exit code.

## Install

```bash
pip install findmyjob
```

## Quick example

=== "Dork search"

    ```bash
    findmyjob "backend engineer" -c br -l remote --db ~/findmyjob.db
    ```

=== "ATS JSON APIs"

    ```bash
    findmyjob ats discover "backend engineer" -c br -o companies.json
    findmyjob ats fetch -t companies.json --db ~/findmyjob.db
    ```

=== "Python"

    ```python
    from findmyjob import search_ddg, filter_jobs, save_to_db

    jobs = search_ddg('site:boards.greenhouse.io "backend engineer"', 10, None)
    save_to_db(filter_jobs(jobs, max_days=7), "findmyjob.db")
    ```

## Where to go next

- [Installation](installation.md) - install from PyPI, source or for development.
- [Quickstart](quickstart.md) - a five-minute walkthrough.
- [CLI reference](cli.md) - every command and flag.
- [ATS JSON APIs](ats.md) - the structured, production-friendly workflow.
- [Data model](data-model.md) - the fields in JSON, CSV, XLSX and SQLite.
- [Python API](python-api.md) - use FindMyJob as a library.
- [Production](production.md) - running it for a job-board portal.
- [Troubleshooting](troubleshooting.md) - common issues and FAQ.

## License

MIT. See [LICENSE](https://github.com/BrunoMoreno/findmyjob/blob/main/LICENSE).
