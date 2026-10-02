"""FindMyJob - Job search via dorks and public ATS JSON APIs."""

__version__ = "0.2.2"

__all__ = [
    "main",
    "search_ddg",
    "search_google",
    "plan_queries",
    "filter_jobs",
    "extract_company",
    "normalize_url",
    "parse_posted_date",
    "save_json",
    "save_csv",
    "save_xlsx",
    "init_db",
    "save_to_db",
    "db_stats",
    "db_export",
    "db_purge",
    "record_run",
    "db_runs",
    "mark_stale",
    "mark_closed",
    # Data model
    "JobPosting",
    # ATS JSON APIs
    "fetch_greenhouse",
    "fetch_lever",
    "fetch_ashby",
    "fetch_smartrecruiters",
    "fetch_targets",
    "load_targets",
    "extract_ats_target",
    "extract_ats_targets",
    "discover_targets",
    "save_targets",
    "AtsError",
]

from .ats import (
    AtsError,
    fetch_ashby,
    fetch_greenhouse,
    fetch_lever,
    fetch_smartrecruiters,
    fetch_targets,
    load_targets,
)
from .cli import (
    db_export,
    db_purge,
    db_runs,
    db_stats,
    extract_company,
    filter_jobs,
    init_db,
    main,
    mark_closed,
    mark_stale,
    normalize_url,
    parse_posted_date,
    plan_queries,
    record_run,
    save_csv,
    save_json,
    save_to_db,
    save_xlsx,
    search_ddg,
    search_google,
)
from .discover import discover_targets, extract_ats_target, extract_ats_targets, save_targets
from .models import JobPosting
