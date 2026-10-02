"""JobSearch - Buscador de vagas via dorks."""

__version__ = "0.1.0"
__all__ = ["main", "search_ddg", "search_google", "plan_queries"]

from .cli import (
    main,
    search_ddg,
    search_google,
    plan_queries,
    filter_jobs,
    save_json,
    save_xlsx,
)
