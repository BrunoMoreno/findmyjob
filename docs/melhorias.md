# Analysis and Improvement Plan - FindMyJob

A detailed document with the project diagnosis, identified problems, evolution opportunities and the technical implementation plan by branches.

---

## 1. Project Diagnosis

**FindMyJob** is a job search tool focused on job boards and ATS (Applicant Tracking Systems) via search engine dorks (DuckDuckGo and Google Custom Search). The project has a lean and efficient proposal, but it accumulated some technical inconsistencies, incomplete fields and a lack of automated tests and queries.

---

## 2. Identified Problems and Limitations

### 2.1 Python Version Incompatibility
- **Location:** `pyproject.toml` and `src/findmyjob/cli.py`
- **Problem:** `pyproject.toml` specifies `requires-python = ">=3.8"`, but the code in `cli.py` uses PEP 604 union type annotations (`dict | None`, `list[str] | None`), natively valid only on Python 3.10+. On Python 3.8/3.9 a fatal error occurs when importing the package.
- **Action:** Add `from __future__ import annotations` to the code files for backward compatibility, or update the project's restriction.

### 2.2 Incomplete Code and Side Effect in `filter_jobs`
- **Location:** `src/findmyjob/cli.py` (`filter_jobs`)
- **Problem:**
  1. The `min_date` and `max_date` parameters appear in the function signature and docstring, but have no implementation lines in the function body.
  2. `max_days: int = 3` is the default value. When the user runs `--filter-include term`, the function silently drops any job older than 3 days when a date is available, while a search without filters does not drop it. Also, there is no `--max-days` option on the command line.
- **Action:** Implement the real date filter (`min_date` and `max_date`), adjust the default of `max_days` so it does not unexpectedly filter dates, and expose the `--max-days` CLI flag.

### 2.3 Discarded Data and Empty Columns in SQLite
- **Location:** `src/findmyjob/cli.py` (`search_ddg`, `search_google`, `main`, `save_to_db`)
- **Problem:**
  1. The `body` field returned by DuckDuckGo and the `snippet` returned by Google contain the job summary/description, but they are discarded in the backends.
  2. The SQLite table has `company TEXT` and `description TEXT` columns, but in the main loop (`main`) these fields are not even added to the job dictionary. The database always saves `NULL` in those columns.
  3. Company extraction does not exist, even though it is trivial to extract it from ATS URLs (e.g. `jobs.lever.co/<company>/...`, `boards.greenhouse.io/<company>/...`, `<company>.gupy.io`) and from formatted titles.
- **Action:** Capture `body`/`snippet`, automatically extract the company from URLs and titles, fill the `company` and `description` fields in the main flow and display them in JSON, Excel and SQLite.

### 2.4 Deduplication and Tracking Parameters in URLs
- **Location:** `src/findmyjob/cli.py` (`main`)
- **Problem:** URLs that point to the same job but carry campaign or analytics parameters (e.g. `utm_source`, `utm_medium`, `lever-source`) are treated as distinct jobs, generating duplicates in the in-memory set and in the SQLite database.
- **Action:** Implement a URL normalization function (removing UTMs and known tracking parameters).

### 2.5 SQLite Export and Tooling
- **Location:** `src/findmyjob/cli.py`
- **Problem:**
  1. The user saves to SQLite with `--db`, but the tool offers no commands to list or analyze what was saved.
  2. Lack of a CSV format, which is standard, lightweight and free of extra dependencies.
  3. Interactive mode does not ask about using the SQLite database.
- **Action:**
  - Add support for CSV export (`--csv`).
  - Add CLI utilities: `--db-stats` (database statistics), `--db-list` (list recent jobs) and `--db-export` (export from the database to a file).
  - Include a question about `--db` in interactive mode.

### 2.6 Test Coverage and CI/CD
- **Location:** `tests/test_main.py` and `.github/workflows/`
- **Problem:**
  1. No database function (`save_to_db`, `_ensure_schema`, `_get_db_path`) has unit tests.
  2. The current tests pollute the terminal with DuckDuckGo retry logs during execution.
  3. There is no GitHub Actions workflow to run the test suite automatically on PRs and pushes (only the PyPI publish one on releases).
- **Action:** Add complete SQLite and new feature tests, silence output in test mocks and create the `.github/workflows/tests.yml` CI workflow.

### 2.7 Repository Maintenance and Configuration
- **Location:** `.gitignore` and `src/findmyjob/__init__.py`
- **Problem:**
  1. `.gitignore` does not include database files (`*.db`, `*.sqlite`, `*.sqlite3`).
  2. `src/findmyjob/__init__.py` did not update `__all__` with the new public functions and exceptions.
- **Action:** Update `.gitignore` and align `__all__`.

---

## 3. Implementation Plan by Branches

To keep the Git history clean, modular and easy to review, the implementation will be carried out in the following branches:

1. **`fix/compat-exports-gitignore`**:
   - Add `from __future__ import annotations`.
   - Update `__all__` and exports in `src/findmyjob/__init__.py`.
   - Update `.gitignore` to ignore SQLite databases (`*.db`, `*.sqlite`, `*.sqlite3`).

2. **`feat/data-enrichment-company-description`**:
   - Capture `body`/`snippet` as description in `search_ddg` and `search_google`.
   - Implement automatic company extraction (`extract_company`) from ATS links and titles.
   - Implement URL normalization (`normalize_url`) for clean deduplication.
   - Integrate `company` and `description` into the main flow, SQLite and the Excel columns with dynamic widths.
   - Add unit tests for the new functions.

3. **`fix/filter-jobs-and-date-handling`**:
   - Implement real support for `min_date` and `max_date` in `filter_jobs`.
   - Make the age filter optional (`max_days: int | None = None`).
   - Add the `--max-days` CLI flag.
   - Add specific unit tests for all date filter scenarios.

4. **`feat/csv-export-and-db-tools`**:
   - Implement CSV export (`save_csv` and the `--csv` flag).
   - Implement database utilities: `--db-stats`, `--db-list` and `--db-export`.
   - Update interactive mode to include the SQLite database option.
   - Add unit tests for the SQLite layer and CSV exporter.

5. **`ci/github-actions-test-workflow`**:
   - Create the `.github/workflows/tests.yml` workflow with a Python version matrix.
   - Silence output in the retry tests.
   - Update `README.md` with the new flags and examples.
