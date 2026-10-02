# Troubleshooting

## The database file is not created

Since 0.2.1, passing `--db` always creates the file and schema, even when no
jobs are found. If it is still missing, check:

- the path is writable and its parent directories can be created;
- the run did not fail before reaching the database step (look at the logs and
  the exit code);
- you actually passed `--db PATH`.

You can create it directly from Python:

```python
from findmyjob import init_db
init_db("findmyjob.db")
```

## The search returns no results

- **DuckDuckGo rate limiting**: the default backend is best-effort. Add
  `--delay`, reduce `-m/--max`, or retry later. The Google backend
  (`-b google`) is more stable if you have credentials.
- **`--strict-dates`**: on the DuckDuckGo backend most results have no date, so
  strict mode can drop everything. Use the [ATS APIs](ats.md) for reliable
  dates, or drop `--strict-dates`.
- **Filters**: `--filter-include` requires the keyword to be in the *title*.

Exit code `2` means every query failed.

## A company returns 0 jobs in `ats fetch`

Almost always a **slug mismatch**, not an empty board. Verify the slug in the
provider URL:

- Greenhouse: `https://boards.greenhouse.io/<slug>`
- Lever: `https://jobs.lever.co/<slug>`
- Ashby: `https://jobs.ashbyhq.com/<slug>`
- SmartRecruiters: `https://jobs.smartrecruiters.com/<companyId>`

SmartRecruiters ids are case-insensitive but exact in practice (`Accor`, not
`accor`).

## `company` is empty or wrong

Company extraction is **best effort**. ATS/board URLs are reliable; the
title-derived heuristic is not, and rejects work-model, seniority and
location segments. Treat the column as a hint, not a key. Maintain your own
company registry for a portal.

## Google backend complains about credentials

Set both variables:

```bash
export GOOGLE_API_KEY="your_key"
export GOOGLE_CX="your_cx"
```

Without them, `search_google` raises `SearchError`.

## `openpyxl is not installed`

XLSX generation is optional and imported lazily:

```bash
pip install openpyxl
```

The JSON/CSV/database outputs still work without it.

## Colors or noise in logs

- `--no-color` disables ANSI colors; the `NO_COLOR` environment variable also
  disables them, as does a non-terminal stdout.
- `-q/--quiet` suppresses progress output and retry notices.
- `--log-file` appends to a file; `-v/--verbose` sets DEBUG level.

## Duplicate jobs across sources

Deduplication uses the normalized URL, so the *same job on different boards*
still appears more than once. Cross-source deduplication needs matching on
`(company, title, location)` — see the
[production guide](production.md#identity-and-deduplication).
