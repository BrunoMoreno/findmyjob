"""JobSearch - Buscador de vagas via dorks."""

__version__ = "0.2.0"
__all__ = [
    "main",
    "search_ddg",
    "search_google",
    "plan_queries",
    "filter_jobs",
    "save_json",
    "save_xlsx",
    "save_to_db",
    "db_stats",
    "db_export",
    "db_purge",
    "normalize_url",
    "parse_posted_date",
]

from .cli import (
    db_export,
    db_purge,
    db_stats,
    filter_jobs,
    main,
    normalize_url,
    parse_posted_date,
    plan_queries,
    save_json,
    save_to_db,
    save_xlsx,
    search_ddg,
    search_google,
)
