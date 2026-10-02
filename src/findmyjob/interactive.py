"""Interactive prompt flow used when no role is passed on the command line."""

from __future__ import annotations

import argparse
import re
from datetime import datetime

from .config import COUNTRIES
from .console import paint


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def default_basename(role: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-") or "jobs"
    return f"jobs_{slug}_{datetime.now():%Y%m%d_%H%M}"


def interactive_prompts(args: argparse.Namespace) -> None:
    print(paint("=== Job search ===", "bold", "cyan"), "\n")
    while not args.role:
        args.role = ask("What role are you looking for? (e.g. backend engineer)")

    print(paint("\nSearch scope:", "bold"))
    print("  1) General (worldwide)")
    print("  2) A specific country")
    if ask("Option", "1") == "2":
        print("  Countries: " + ", ".join(f"{k} ({v['names'][0]})" for k, v in COUNTRIES.items()))
        code = ask("Country code", "br").lower()
        if code in COUNTRIES:
            args.country = code
        else:
            print(paint(f"  [warning] unknown country '{code}', using a general search.", "yellow"))
        locs = ask("Refine by city/remote (optional, comma-separated)", "")
    else:
        args.country = None
        locs = ask("Location(s), comma-separated", "remote, latam")
    args.local = [x.strip() for x in locs.split(",") if x.strip()]

    print(paint("\nWhere to search?", "bold"))
    print("  1) Job boards (Indeed, LinkedIn, Glassdoor + local ones)")
    print("  2) Company ATS (Greenhouse, Lever, Workday, ...)")
    print("  3) All")
    args.group = {"1": "boards", "2": "ats", "3": "all"}.get(ask("Option", "3"), "all")

    max_raw = ask("Results per query", str(args.max))
    args.max = int(max_raw) if max_raw.isdigit() else args.max

    # Additional filters
    print(paint("\nAdditional filters (optional):", "bold"))
    include = ask("Keywords to include (comma)", "")
    args.filter_include = [x.strip() for x in include.split(",") if x.strip()]
    exclude = ask("Keywords to exclude (comma)", "")
    args.filter_exclude = [x.strip() for x in exclude.split(",") if x.strip()]

    max_days_raw = ask("Maximum job age in days (0 disables)", str(args.max_days))
    if max_days_raw.isdigit():
        args.max_days = int(max_days_raw)

    args.output = ask("Base name for the files (generates .json and .xlsx)",
                      default_basename(args.role))

    print(paint("\nSave to a SQLite database?", "bold"))
    db_path = ask("Database path (empty = no)", "")
    args.db = db_path or None

    args.csv = ask("Also save CSV? (y/N)", "n").lower() in ("s", "sim", "y", "yes")
    print()
