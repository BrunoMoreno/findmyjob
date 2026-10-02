# ATS JSON APIs

Search dorks only return a snippet, so the posting date is unreliable. The
public ATS JSON APIs return structured data (including a real posting date) and
need **one request per company** instead of one query per board — much faster
and more accurate for monitoring a fixed list of companies.

## Supported providers

| Provider | Endpoint | Company identifier |
|----------|----------|--------------------|
| Greenhouse | `boards-api.greenhouse.io` | board token (`stripe`) |
| Lever | `api.lever.co` | company slug (`spotify`) |
| Ashby | `api.ashbyhq.com` | job board name (`openai`) |
| SmartRecruiters | `api.smartrecruiters.com` | company id (`Accor`) |

!!! note
    Workday and Workable appear in the dork domains (`-g ats`) but are **not**
    available through the JSON API integration.

## 1. Discover companies

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

`load_targets` also accepts a flat list of `"provider/slug"` strings:

```json
["greenhouse/stripe", "lever/spotify"]
```

## 2. Fetch jobs

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
`--no-xlsx`, `--db`, `-q/--quiet`, `-o/--output`), plus:

| Flag | Description |
|------|-------------|
| `-t, --targets` | Targets file (default: `companies.json`) |
| `--provider` | Only these providers (repeatable) |
| `--retries` | Attempts per request (default: 3) |
| `--timeout` | Request timeout in seconds (default: 20) |
| `--delay` | Seconds between companies (default: 0) |

## Date filtering

Because the APIs return real posting dates, `--max-days` and `--strict-dates`
are meaningful here — unlike the default DuckDuckGo backend, where most results
have no date at all.

```bash
findmyjob ats fetch -t companies.json --max-days 7 --strict-dates
```

## Exit codes

`ats fetch` returns `2` when **every** target failed (useful for monitoring)
and `1` for fatal errors such as a missing or invalid targets file.

## The `company` column

The `company` column is best effort: ATS URLs are reliable (the slug is
prettified), while title-derived names are not and may be empty when no company
can be identified.

## Troubleshooting

A company that returns **0 jobs** is usually a slug mismatch, not an empty
board. Confirm the slug against the provider URL, for example
`https://jobs.lever.co/<slug>` or `https://boards.greenhouse.io/<slug>`.
