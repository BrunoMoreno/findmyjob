# Data model

Reference for every field FindMyJob produces: JSON, XLSX, CSV and SQLite.

## Job object

Both the dork search and the ATS fetchers produce dictionaries with the same
shape. Not every field is always populated.

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Job title |
| `link` | string | URL of the posting |
| `company` | string | Best-effort company name (may be empty) |
| `location` | string | Location as reported by the source |
| `posted_at` | string \| null | Posting date (ISO 8601, or a provider string). Real values come from the ATS APIs or Google CSE |
| `description` | string | Description text (ATS HTML stripped, truncated to 4000 chars; otherwise the snippet) |
| `snippet` | string | Raw snippet (same as `description` when there is nothing better) |
| `domain` | string | Board/ATS domain (e.g. `boards.greenhouse.io`) |
| `source` | string | Source label: the domain for dorks, the provider for ATS |
| `query` | string | The dork that found it, or `ats:<provider>/<slug>` |

## JSON

The `.json` file contains the search metadata plus the jobs.

```json
{
  "role": "backend engineer",
  "scope": "Brazil",
  "country": "br",
  "locations": ["remote"],
  "group": "all",
  "backend": "ddg",
  "filter_include": [],
  "filter_exclude": [],
  "max_days": 3,
  "searched_at": "2026-10-02T11:06:06",
  "total": 3,
  "jobs": [
    {
      "title": "Backend Engineer",
      "link": "https://boards.greenhouse.io/acme/jobs/123",
      "company": "Acme",
      "location": "Remote - Brazil",
      "posted_at": "2026-09-30T00:00:00",
      "description": "...",
      "snippet": "...",
      "domain": "boards.greenhouse.io",
      "source": "greenhouse",
      "query": "ats:greenhouse/acme"
    }
  ]
}
```

## XLSX

The `.xlsx` workbook has two sheets:

- **Jobs**: `#`, `Title`, `Company`, `Link` (hyperlink), `Domain`, `Location`,
  `Query`, `Description`. Frozen header, auto-filter and sized columns.
- **Search**: the metadata above as key/value pairs, plus `total`.

## CSV

Enabled with `--csv`. Columns, in order:

```
title, company, link, domain, location, query, posted_at, description
```

The file is written as UTF-8 with BOM (`utf-8-sig`) so spreadsheet apps open it
correctly.

## SQLite

Created with `--db`. Table `jobs`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER | Primary key, autoincrement |
| `title` | TEXT | Not null |
| `link` | TEXT | Not null, unique |
| `link_key` | TEXT | Normalized URL; unique index (dedup key) |
| `source` | TEXT | Domain or ATS provider |
| `domain` | TEXT | Board/ATS domain |
| `location` | TEXT | |
| `query` | TEXT | Dork or `ats:<provider>/<slug>` |
| `posted_at` | TEXT | ISO 8601 when known |
| `salary` | TEXT | Reserved; not populated by the current fetchers |
| `company` | TEXT | Best-effort |
| `description` | TEXT | |
| `first_seen_at` | TEXT | ISO 8601, set on insert |
| `last_seen_at` | TEXT | ISO 8601, refreshed every run |
| `created_at` | TEXT | Not null, set on insert |
| `updated_at` | TEXT | Not null |

Indexes: `idx_jobs_link_key` (unique), `idx_jobs_created_at`, `idx_jobs_source`.
