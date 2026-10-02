"""
Search for jobs via dorks (site:domain "role" "location") or ATS JSON APIs.

Interactive mode (asks everything):
    findmyjob

Direct mode:
    findmyjob "backend engineer" -l remote -l latam            # general
    findmyjob "backend engineer" -c br                         # Brazil only
    findmyjob "backend engineer" -c br -l remote --group ats   # Brazil + remote
    findmyjob --list-countries

ATS JSON APIs:
    findmyjob ats discover "backend engineer" -c br -o companies.json
    findmyjob ats fetch -t companies.json --db findmyjob.db

Database:
    findmyjob db stats
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Re-exported so `from findmyjob.cli import ...` keeps working (and so the
# public API stays stable for existing scripts).
from . import __version__
from .ats import PROVIDERS, AtsError, fetch_targets, load_targets
from .config import ATS, BOARDS, COUNTRIES, GROUPS
from .console import log, paint, setup_logging
from .dates import filter_jobs, parse_posted_date
from .db import (
    _get_db_path,
    db_export,
    db_purge,
    db_runs,
    db_stats,
    init_db,
    mark_closed,
    mark_stale,
    record_run,
    save_to_db,
)
from .dedup import normalize_url
from .discover import discover_targets, extract_ats_target, extract_ats_targets, save_targets
from .enrich import extract_company
from .interactive import ask, default_basename, interactive_prompts
from .metrics import emit_run_summary, run_summary
from .models import JobPosting
from .output import save_csv, save_json, save_xlsx
from .search import (
    BACKENDS,
    SearchError,
    country_term,
    domains_for,
    plan_queries,
    search_ddg,
    search_google,
)

__all__ = [
    "ATS", "BOARDS", "COUNTRIES", "GROUPS", "PROVIDERS", "BACKENDS",
    "AtsError", "SearchError", "ask", "country_term", "db_command", "db_export",
    "db_purge", "db_runs", "db_stats", "default_basename", "discover_targets", "domains_for",
    "extract_ats_target", "extract_ats_targets", "extract_company", "fetch_targets",
    "filter_jobs", "init_db", "interactive_prompts", "load_targets", "main",
    "JobPosting",
    "mark_closed", "mark_stale",
    "normalize_url",
    "parse_posted_date", "plan_queries", "record_run", "save_csv", "save_json", "save_targets",
    "save_to_db", "save_xlsx", "search_ddg", "search_google",
]


# ------------------------------------------------------------- common args --

def _add_version_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-V", "--version", action="version",
                        version=f"findmyjob {__version__}")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-color", action="store_true", help="disable colors")
    parser.add_argument("-q", "--quiet", action="store_true", help="suppress progress output")
    parser.add_argument("-v", "--verbose", action="store_true", help="detailed logging")
    parser.add_argument("--log-file", help="log file (append)")
    parser.add_argument("--log-json", action="store_true",
                        help="write logs as JSON lines (structured logging)")
    parser.add_argument("--metrics-file",
                        help="write a JSON run summary to this file")
    _add_version_arg(parser)


# -------------------------------------------------------------- job output --

def _dedup_normalized(jobs: list[dict]) -> list[dict]:
    """In-run deduplication keyed on the normalized (tracking-free) URL."""
    seen: set[str] = set()
    unique: list[dict] = []
    for job in jobs:
        link = job.get("link", "")
        key = normalize_url(link) if link else ""
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def _apply_filters(args: argparse.Namespace, jobs: list[dict]) -> list[dict]:
    has_filter = (getattr(args, "filter_include", None)
                  or getattr(args, "filter_exclude", None)
                  or getattr(args, "max_days", 0) > 0
                  or getattr(args, "min_date", None)
                  or getattr(args, "max_date", None))
    if not has_filter:
        return jobs
    before = len(jobs)
    jobs = filter_jobs(
        jobs,
        keywords=args.filter_include,
        exclude_keywords=args.filter_exclude,
        max_days=args.max_days,
        min_date=args.min_date,
        max_date=args.max_date,
        keep_unknown_dates=not args.strict_dates,
    )
    log.info("Filters applied: %d -> %d jobs", before, len(jobs))
    return jobs


def _write_outputs(args: argparse.Namespace, jobs: list[dict], meta: dict,
                   base_default: str) -> list[str]:
    base = args.output or base_default
    base = re.sub(r"\.(json|xlsx?|csv)$", "", base, flags=re.IGNORECASE)
    saved: list[str] = []
    if not getattr(args, "no_json", False):
        save_json(f"{base}.json", meta, jobs)
        saved.append(f"{base}.json")
    if not getattr(args, "no_xlsx", False) and save_xlsx(f"{base}.xlsx", meta, jobs):
        saved.append(f"{base}.xlsx")
    if getattr(args, "csv", False) and save_csv(f"{base}.csv", jobs):
        saved.append(f"{base}.csv")
    return saved


# ------------------------------------------------------------- db command --

def _confirm(prompt: str) -> bool:
    """Ask a yes/no question on the terminal (default: no)."""
    resp = input(f"{prompt} [y/N]: ").strip().lower()
    return resp in ("s", "y", "sim", "yes")


def db_command(argv: list[str]) -> int:
    """Subcommands to inspect/manage the database: stats, export, purge,
    runs, mark-stale and mark-closed."""
    parser = argparse.ArgumentParser(prog="findmyjob db",
                                     description="SQLite database utilities")
    _add_version_arg(parser)
    parser.add_argument("--db", help="database path (default: ./findmyjob.db)")
    sub = parser.add_subparsers(dest="action", required=True)

    p_stats = sub.add_parser("stats", help="show database statistics")
    p_stats.add_argument("--json", action="store_true", help="JSON output")

    p_export = sub.add_parser("export", help="export jobs")
    p_export.add_argument("-o", "--output", help="output file (default: stdout)")
    p_export.add_argument("--format", choices=["json", "csv"], default="json")
    p_export.add_argument("--limit", type=int, help="maximum number of jobs")
    p_export.add_argument("--since-days", type=int, help="only the last N days")
    p_export.add_argument("--status", choices=["active", "stale", "closed"],
                          help="only jobs with this status")

    p_purge = sub.add_parser("purge", help="remove old jobs")
    p_purge.add_argument("--older-than", type=int, metavar="DAYS",
                         help="remove jobs last seen more than N days ago")
    p_purge.add_argument("-y", "--yes", action="store_true",
                         help="do not ask for confirmation")

    p_runs = sub.add_parser("runs", help="list recent ingest runs")
    p_runs.add_argument("--limit", type=int, default=20,
                        help="number of runs (default: 20)")
    p_runs.add_argument("--json", action="store_true", help="JSON output")

    p_stale = sub.add_parser("mark-stale", help="mark jobs not seen recently as stale")
    p_stale.add_argument("--older-than", type=int, required=True, metavar="DAYS",
                         help="jobs last seen more than N days ago")
    p_stale.add_argument("--source", help="only jobs from this source/provider")
    p_stale.add_argument("-y", "--yes", action="store_true",
                         help="do not ask for confirmation")

    p_closed = sub.add_parser("mark-closed", help="mark stale jobs as closed")
    p_closed.add_argument("--older-than", type=int, required=True, metavar="DAYS",
                          help="jobs stale for more than N days")
    p_closed.add_argument("--source", help="only jobs from this source/provider")
    p_closed.add_argument("-y", "--yes", action="store_true",
                          help="do not ask for confirmation")

    args = parser.parse_args(argv)
    db = args.db

    if args.action == "stats":
        stats = db_stats(db)
        if args.json:
            print(json.dumps(stats, ensure_ascii=False, indent=2))
            return 0
        print(paint("Database:", "bold"), _get_db_path(db))
        print(paint("Total jobs:", "bold"), stats["total"])
        print("First:", stats["first_seen"] or "-")
        print("Last: ", stats["last_seen"] or "-")
        if stats["by_source"]:
            print("\n" + paint("By source:", "bold"))
            for src, count in stats["by_source"]:
                print(f"  {count:>5}  {src}")
        if stats.get("by_status"):
            print("\n" + paint("By status:", "bold"))
            for status, count in stats["by_status"]:
                print(f"  {count:>5}  {status}")
        if stats["by_day"]:
            print("\n" + paint("By day (recent):", "bold"))
            for day, count in stats["by_day"]:
                print(f"  {count:>5}  {day}")
        return 0

    if args.action == "export":
        content = db_export(db, fmt=args.format, limit=args.limit,
                            since_days=args.since_days, status=args.status)
        if args.output:
            Path(args.output).write_text(content, encoding="utf-8")
            print(f"Exported to {args.output}")
        else:
            print(content)
        return 0

    if args.action == "purge":
        if not args.yes:
            target = (f"jobs older than {args.older_than} days"
                      if args.older_than else "ALL jobs")
            if not _confirm(f"Confirm removal of {target}?"):
                print("Cancelled.")
                return 1
        deleted = db_purge(db, older_than_days=args.older_than)
        print(f"{deleted} job(s) removed.")
        return 0

    if args.action == "runs":
        runs = db_runs(db, limit=args.limit)
        if args.json:
            print(json.dumps(runs, ensure_ascii=False, indent=2))
            return 0
        if not runs:
            print("No runs recorded yet.")
            return 0
        print(paint("Recent runs:", "bold"))
        for run in runs:
            print(f"  #{run['id']:<4} {run['finished_at']}  {run['kind']:<6} "
                  f"{run['status']:<7} fetched={run['fetched']} "
                  f"inserted={run['inserted']} errors={run['errors']}  "
                  f"{run['scope'] or ''}")
        return 0

    if args.action == "mark-stale":
        where = f" from {args.source}" if args.source else ""
        if not args.yes and not _confirm(
                f"Mark active jobs{where} not seen in {args.older_than} days as stale?"):
            print("Cancelled.")
            return 1
        changed = mark_stale(db, args.older_than, source=args.source)
        print(f"{changed} job(s) marked as stale.")
        return 0

    if args.action == "mark-closed":
        where = f" from {args.source}" if args.source else ""
        if not args.yes and not _confirm(
                f"Mark jobs{where} stale for {args.older_than} days as closed?"):
            print("Cancelled.")
            return 1
        changed = mark_closed(db, args.older_than, source=args.source)
        print(f"{changed} job(s) marked as closed.")
        return 0

    return 1  # pragma: no cover


# ------------------------------------------------------------- ats command --

def _ats_fetch(args: argparse.Namespace) -> int:
    started = datetime.now().isoformat(timespec="seconds")
    started_mono = time.monotonic()
    targets_path = Path(args.targets)
    if not targets_path.exists():
        log.error("targets file not found: %s", targets_path)
        return 1
    try:
        targets = load_targets(targets_path)
    except (OSError, ValueError) as e:
        log.error("invalid targets file: %s", e)
        return 1

    if args.provider:
        targets = {p: targets.get(p, []) for p in args.provider}
        targets = {p: slugs for p, slugs in targets.items() if slugs}

    total_targets = sum(len(v) for v in targets.values())
    if not total_targets:
        log.warning("no targets to fetch from %s", targets_path)
        return 0

    log.info("Fetching %d target(s) from %s", total_targets, targets_path)
    jobs, errors = fetch_targets(targets, retries=args.retries,
                                 timeout=args.timeout, delay=args.delay,
                                 concurrency=args.concurrency,
                                 per_host=args.per_host)
    log.info("Fetched %d job(s); %d target(s) failed", len(jobs), len(errors))

    jobs = _dedup_normalized(jobs)
    jobs = _apply_filters(args, jobs)

    meta = {
        "role": "",
        "scope": "ats",
        "targets": str(targets_path),
        "filter_include": args.filter_include,
        "filter_exclude": args.filter_exclude,
        "max_days": args.max_days,
        "searched_at": datetime.now().isoformat(timespec="seconds"),
    }
    base_default = f"ats_jobs_{datetime.now():%Y%m%d_%H%M}"
    saved = _write_outputs(args, jobs, meta, base_default)

    inserted = 0
    if args.db:
        try:
            init_db(args.db)
            inserted = save_to_db(jobs, args.db)
            log.info("%d new jobs saved to the database %s", inserted, _get_db_path(args.db))
        except Exception as e:  # noqa: BLE001
            log.error("failed to save to the database: %s", e)
            errors.append(str(e))

    run_status = ("failed" if total_targets and len(errors) >= total_targets
                  else "partial" if errors else "ok")
    summary = run_summary(
        started=started_mono, kind="ats", scope=str(targets_path),
        targets=total_targets, fetched=len(jobs), inserted=inserted,
        errors=len(errors), status=run_status, providers=sorted(targets))

    if args.db:
        try:
            record_run(args.db, "ats", scope=str(targets_path),
                       targets=total_targets, fetched=len(jobs), inserted=inserted,
                       errors=len(errors), status=run_status, started_at=started,
                       details={"providers": sorted(targets),
                                "duration_s": summary["duration_s"]})
        except Exception as e:  # noqa: BLE001
            log.error("failed to record run: %s", e)

    emit_run_summary(summary, metrics_file=args.metrics_file)

    log.info("%d unique jobs found.", len(jobs))
    if saved:
        log.info("Files saved: %s", ", ".join(saved))

    # Exit code 2 when every target failed (useful for cronjobs).
    if total_targets and len(errors) >= total_targets:
        return 2
    return 0


def _ats_discover(args: argparse.Namespace) -> int:
    country = COUNTRIES.get(args.country) if args.country else None
    targets, errors = discover_targets(
        args.role, country, args.local, args.max, backend=args.backend,
        retries=args.retries, delay=args.delay)

    if not targets:
        log.warning("no ATS targets found.")
        for err in errors:
            log.error("%s", err)
        return 1 if errors else 0

    if args.dry_run:
        print(json.dumps(targets, ensure_ascii=False, indent=2))
        return 0

    merged = save_targets(args.output, targets, merge=args.merge)
    log.info("%d new target(s) written to %s", sum(len(v) for v in targets.values()),
             args.output)
    log.info("Total targets in the file: %d", sum(len(v) for v in merged.values()))
    return 0


def ats_command(argv: list[str]) -> int:
    """Subcommands for the public ATS JSON APIs."""
    common = argparse.ArgumentParser(add_help=False)
    _add_common_args(common)

    parser = argparse.ArgumentParser(prog="findmyjob ats",
                                     description="Public ATS JSON APIs")
    _add_version_arg(parser)
    sub = parser.add_subparsers(dest="action", required=True)

    p_fetch = sub.add_parser("fetch", parents=[common],
                             help="fetch jobs from the ATS JSON APIs")
    p_fetch.add_argument("-t", "--targets", default="companies.json",
                         help="target companies JSON (default: companies.json)")
    p_fetch.add_argument("--provider", action="append", choices=PROVIDERS,
                         help="only fetch from these providers (repeatable)")
    p_fetch.add_argument("--db", help="save results to a SQLite database")
    p_fetch.add_argument("-o", "--output", help="base name for output files")
    p_fetch.add_argument("--csv", action="store_true", help="also save a CSV file")
    p_fetch.add_argument("--no-json", action="store_true", help="do not save a JSON file")
    p_fetch.add_argument("--no-xlsx", action="store_true", help="do not save an XLSX file")
    p_fetch.add_argument("--filter-include", nargs="+", default=[],
                         help="keywords that must be in the title")
    p_fetch.add_argument("--filter-exclude", nargs="+", default=[],
                         help="keywords that must NOT be in the title")
    p_fetch.add_argument("--max-days", type=int, default=30,
                         help="maximum job age in days (0 disables; default: 30)")
    p_fetch.add_argument("--strict-dates", action="store_true",
                         help="drop jobs without an identifiable date")
    p_fetch.add_argument("--min-date", help="minimum posting date (YYYY-MM-DD)")
    p_fetch.add_argument("--max-date", help="maximum posting date (YYYY-MM-DD)")
    p_fetch.add_argument("--retries", type=int, default=3,
                         help="number of attempts per request")
    p_fetch.add_argument("--timeout", type=float, default=20.0, help="request timeout (s)")
    p_fetch.add_argument("--delay", type=float, default=0.0,
                         help="seconds between request starts")
    p_fetch.add_argument("--concurrency", type=int, default=1,
                         help="number of companies to fetch in parallel (default: 1)")
    p_fetch.add_argument("--per-host", type=int, default=5,
                         help="max simultaneous requests per ATS host (default: 5)")

    p_disc = sub.add_parser("discover", parents=[common],
                            help="find ATS companies via search dorks")
    p_disc.add_argument("role", help='role, e.g. "backend engineer"')
    p_disc.add_argument("-c", "--country", choices=COUNTRIES,
                        help="restrict to one country")
    p_disc.add_argument("-l", "--local", action="append", default=[],
                        help="extra location/term (repeatable)")
    p_disc.add_argument("-m", "--max", type=int, default=10, help="results per dork")
    p_disc.add_argument("-b", "--backend", choices=BACKENDS, default="ddg")
    p_disc.add_argument("-o", "--output", default="companies.json",
                        help="targets file to write (default: companies.json)")
    p_disc.add_argument("--merge", action="store_true",
                        help="merge with an existing targets file")
    p_disc.add_argument("--dry-run", action="store_true",
                        help="print the targets instead of writing a file")
    p_disc.add_argument("--retries", type=int, default=3)
    p_disc.add_argument("--delay", type=float, default=2.0,
                        help="seconds between dorks")

    args = parser.parse_args(argv)

    if args.no_color:
        from . import console
        console.USE_COLOR = False
    setup_logging(log_file=args.log_file, quiet=args.quiet, verbose=args.verbose,
                  json_format=args.log_json)

    if args.action == "fetch":
        return _ats_fetch(args)
    if args.action == "discover":
        return _ats_discover(args)
    return 1  # pragma: no cover


# -------------------------------------------------------------------- main --

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Search for jobs with search dorks")
    _add_version_arg(p)
    p.add_argument("role", nargs="?", help='role, e.g. "backend engineer" (omit for interactive mode)')
    p.add_argument("-c", "--country", choices=COUNTRIES,
                   help="restrict the search to one country (omit for a general search)")
    p.add_argument("-l", "--local", action="append", default=[],
                   help="extra location/term (repeat for several). With -c it refines the country (city, remote)")
    p.add_argument("-g", "--group", choices=GROUPS, default="all")
    p.add_argument("-b", "--backend", choices=BACKENDS, default="ddg")
    p.add_argument("-m", "--max", type=int, default=8, help="results per query")
    p.add_argument("-o", "--output", help="base name for output files, generates .json and .xlsx")
    p.add_argument("-i", "--interactive", action="store_true", help="force interactive mode")
    p.add_argument("--delay", type=float, default=2.0, help="seconds between queries")
    p.add_argument("--retries", type=int, default=3, help="number of attempts on error")
    p.add_argument("--show-queries", action="store_true", help="only print the queries")
    p.add_argument("--no-color", action="store_true", help="disable colors")
    p.add_argument("--list-countries", action="store_true", help="list the available countries")
    p.add_argument("--filter-include", nargs="+", default=[],
                   help="keywords that must be in the title")
    p.add_argument("--filter-exclude", nargs="+", default=[],
                   help="keywords that must NOT be in the title")
    p.add_argument("--max-days", type=int, default=3,
                   help="maximum job age in days (0 disables; default: 3)")
    p.add_argument("--strict-dates", action="store_true",
                   help="drop jobs without an identifiable date")
    p.add_argument("--min-date", help="minimum posting date (YYYY-MM-DD)")
    p.add_argument("--max-date", help="maximum posting date (YYYY-MM-DD)")
    p.add_argument("--db", help="save results to a SQLite database (e.g. findmyjob.db)")
    p.add_argument("--csv", action="store_true", help="also save a CSV file")
    p.add_argument("--no-json", action="store_true", help="do not save a JSON file")
    p.add_argument("--no-xlsx", action="store_true", help="do not save an XLSX file")
    p.add_argument("-q", "--quiet", action="store_true", help="suppress progress output")
    p.add_argument("-v", "--verbose", action="store_true", help="detailed logging")
    p.add_argument("--log-file", help="log file (append)")
    p.add_argument("--log-json", action="store_true",
                   help="write logs as JSON lines (structured logging)")
    p.add_argument("--metrics-file", help="write a JSON run summary to this file")
    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Subcommands: findmyjob db <...>, findmyjob ats <...>
    if argv and argv[0] == "db":
        return db_command(argv[1:])
    if argv and argv[0] == "ats":
        return ats_command(argv[1:])

    p = _build_parser()
    args = p.parse_args(argv)

    if args.no_color:
        from . import console
        console.USE_COLOR = False

    setup_logging(log_file=args.log_file, quiet=args.quiet, verbose=args.verbose,
                  json_format=args.log_json)

    if args.list_countries:
        for k, v in COUNTRIES.items():
            print(f"{paint(k, 'bold', 'cyan')}  {v['names'][0]}")
        return 0

    if args.interactive or not args.role:
        interactive_prompts(args)

    country = COUNTRIES.get(args.country) if args.country else None
    plan = plan_queries(args.role, args.local, args.group, country)

    if args.show_queries:
        for item in plan:
            print(item["query"])
        return 0

    scope = country["names"][0] if country else "general"
    log.info("Scope: %s | %d queries", scope, len(plan))
    started = datetime.now().isoformat(timespec="seconds")
    started_mono = time.monotonic()

    from . import console

    search = BACKENDS[args.backend]
    seen: set[str] = set()
    jobs: list[dict] = []
    errors = 0

    try:
        for item in plan:
            if not console.QUIET:
                print("\n" + paint(f"== {item['domain']}", "bold", "cyan"),
                      paint(f"| {item['location']} ==", "yellow"))
                print("   " + paint(item["query"], "dim"))
            try:
                results = search(item["query"], args.max, country,
                                 retries=args.retries)
            except SearchError as e:
                log.error("%s", e)
                errors += 1
                time.sleep(args.delay)
                continue

            new = []
            for r in results:
                link = r.get("link", "")
                key = normalize_url(link) if link else ""
                if not key or key in seen:
                    continue
                seen.add(key)
                new.append(r)
            if not new and not console.QUIET:
                print(paint("   (no new results)", "dim"))
            for r in new:
                snippet = r.get("snippet", "") or ""
                jobs.append({"title": r["title"], "link": r["link"],
                             "domain": item["domain"], "location": item["location"],
                             "query": item["query"],
                             "source": item["domain"],
                             "company": extract_company(r["link"], r["title"]),
                             "description": snippet,
                             "snippet": snippet,
                             "posted_at": r.get("posted_at") or r.get("date")
                             or r.get("published")})
                if not console.QUIET:
                    print(f"   {paint('-', 'green')} {paint(r['title'], 'bold', 'green')}")
                    print("     " + paint(r["link"], "blue", "underline"))
            time.sleep(args.delay)
    except KeyboardInterrupt:
        log.warning("interrupted; saving what was found so far...")

    jobs = _apply_filters(args, jobs)

    meta = {
        "role": args.role,
        "scope": scope,
        "country": args.country or "",
        "locations": args.local,
        "group": args.group,
        "backend": args.backend,
        "filter_include": args.filter_include,
        "filter_exclude": args.filter_exclude,
        "max_days": args.max_days,
        "searched_at": datetime.now().isoformat(timespec="seconds"),
    }
    saved_list = _write_outputs(args, jobs, meta, default_basename(args.role))

    inserted = 0
    if args.db:
        try:
            init_db(args.db)
            inserted = save_to_db(jobs, args.db)
            log.info("%d new jobs saved to the database %s", inserted, _get_db_path(args.db))
        except Exception as e:  # noqa: BLE001
            log.error("failed to save to the database: %s", e)
            errors += 1

    run_status = ("failed" if plan and errors >= len(plan)
                  else "partial" if errors else "ok")
    summary = run_summary(
        started=started_mono, kind="search", scope=scope, targets=len(plan),
        fetched=len(jobs), inserted=inserted, errors=errors, status=run_status,
        role=args.role, backend=args.backend, country=args.country or "")

    if args.db:
        try:
            record_run(args.db, "search", scope=scope, targets=len(plan),
                       fetched=len(jobs), inserted=inserted, errors=errors,
                       status=run_status, started_at=started,
                       details={"role": args.role, "backend": args.backend,
                                "country": args.country or "",
                                "duration_s": summary["duration_s"]})
        except Exception as e:  # noqa: BLE001
            log.error("failed to record run: %s", e)

    emit_run_summary(summary, metrics_file=args.metrics_file)

    log.info("%d unique jobs found.", len(jobs))
    if saved_list:
        log.info("Files saved: %s", ", ".join(saved_list))

    # Exit code: 2 if all queries failed (useful for cronjobs)
    if plan and errors >= len(plan):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
