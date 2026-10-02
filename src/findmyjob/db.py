"""SQLite persistence for search results."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .console import log
from .dedup import normalize_url


def _get_db_path(db: str | None) -> Path:
    if db:
        return Path(db).expanduser().resolve()
    return Path.cwd() / "findmyjob.db"


def _connect(db: str | None) -> sqlite3.Connection:
    db_path = _get_db_path(db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT NOT NULL UNIQUE,
            link_key TEXT,
            source TEXT,
            domain TEXT,
            location TEXT,
            query TEXT,
            posted_at TEXT,
            salary TEXT,
            company TEXT,
            description TEXT,
            provider TEXT,
            external_id TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            status_changed_at TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    # Migration for databases created by earlier versions.
    cols = {row[1] for row in cur.execute("PRAGMA table_info(jobs)")}
    added: set[str] = set()
    for col in ("link_key", "first_seen_at", "last_seen_at", "provider",
                "external_id", "status_changed_at"):
        if col not in cols:
            cur.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")
            added.add(col)
    if "status" not in cols:
        cur.execute("ALTER TABLE jobs ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        added.add("status")
    if added & {"status", "status_changed_at"}:
        cur.execute(
            "UPDATE jobs SET status_changed_at = "
            "COALESCE(status_changed_at, last_seen_at, created_at)"
        )
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_link_key ON jobs(link_key)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_source_external_id "
        "ON jobs(source, external_id)"
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            scope TEXT,
            targets INTEGER NOT NULL DEFAULT 0,
            fetched INTEGER NOT NULL DEFAULT 0,
            inserted INTEGER NOT NULL DEFAULT 0,
            errors INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ok',
            details TEXT,
            started_at TEXT,
            finished_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def init_db(db: str | None = None) -> Path:
    """
    Create the database file and schema if they do not exist.

    Returns the resolved database path. Useful for cronjobs, so the database
    exists even when a run finds no new jobs.
    """
    conn = _connect(db)
    try:
        _ensure_schema(conn)
    finally:
        conn.close()
    return _get_db_path(db)


def save_to_db(jobs: list[dict], db: str | None = None) -> int:
    """
    Save jobs to a SQLite database.

    Deduplicates by normalized URL (without tracking). Returns the number of
    new jobs inserted. Existing jobs get `last_seen_at` updated.
    """
    if not jobs:
        return 0

    conn = _connect(db)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")
        inserted = 0
        for j in jobs:
            link = j.get("link", "")
            if not link:
                continue
            try:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO jobs (
                        title, link, link_key, source, domain, location, query,
                        posted_at, salary, company, description, provider,
                        external_id, status, status_changed_at, first_seen_at,
                        last_seen_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        j.get("title", ""),
                        link,
                        normalize_url(link),
                        j.get("source") or j.get("domain"),
                        j.get("domain") or j.get("source"),
                        j.get("location"),
                        j.get("query"),
                        j.get("posted_at") or j.get("date") or j.get("published"),
                        j.get("salary"),
                        j.get("company"),
                        j.get("snippet") or j.get("description"),
                        j.get("provider"),
                        j.get("external_id"),
                        "active",
                        now,
                        now,
                        now,
                        now,
                        now,
                    ),
                )
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    # Refresh the lifecycle timestamps, backfill identity
                    # columns on rows created by earlier versions, and reopen a
                    # posting that had been marked stale/closed.
                    cur.execute(
                        """
                        UPDATE jobs SET
                            last_seen_at = ?,
                            updated_at = ?,
                            provider = COALESCE(NULLIF(provider, ''), ?),
                            external_id = COALESCE(NULLIF(external_id, ''), ?),
                            status_changed_at = CASE WHEN status <> 'active'
                                THEN ? ELSE status_changed_at END,
                            status = 'active'
                        WHERE link_key = ?
                        """,
                        (
                            now,
                            now,
                            j.get("provider"),
                            j.get("external_id"),
                            now,
                            normalize_url(link),
                        ),
                    )
            except sqlite3.Error as e:
                log.warning("Failed to save job to the database: %s", e)
                continue
        conn.commit()
    finally:
        conn.close()

    return inserted


def db_stats(db: str | None = None) -> dict:
    """Return database statistics."""
    conn = _connect(db)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()
        total = cur.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        first = cur.execute("SELECT MIN(created_at) FROM jobs").fetchone()[0]
        last = cur.execute("SELECT MAX(created_at) FROM jobs").fetchone()[0]
        by_source = cur.execute(
            "SELECT COALESCE(source, domain) AS s, COUNT(*) c FROM jobs "
            "GROUP BY s ORDER BY c DESC"
        ).fetchall()
        by_status = cur.execute(
            "SELECT COALESCE(status, 'active') AS s, COUNT(*) c FROM jobs "
            "GROUP BY s ORDER BY c DESC"
        ).fetchall()
        by_day = cur.execute(
            "SELECT substr(created_at, 1, 10) AS d, COUNT(*) c FROM jobs "
            "GROUP BY d ORDER BY d DESC LIMIT 14"
        ).fetchall()
    finally:
        conn.close()
    return {
        "total": total,
        "first_seen": first,
        "last_seen": last,
        "by_source": [(r["s"], r["c"]) for r in by_source],
        "by_status": [(r["s"], r["c"]) for r in by_status],
        "by_day": [(r["d"], r["c"]) for r in by_day],
    }


def db_export(db: str | None = None, fmt: str = "json", limit: int | None = None,
              since_days: int | None = None, status: str | None = None) -> str:
    """Export jobs from the database as JSON or CSV (returns the text)."""
    import csv
    import io

    conn = _connect(db)
    try:
        _ensure_schema(conn)
        sql = "SELECT * FROM jobs"
        params: list = []
        where: list[str] = []
        if since_days:
            cutoff = (datetime.now() - timedelta(days=since_days)).isoformat(timespec="seconds")
            where.append("created_at >= ?")
            params.append(cutoff)
        if status:
            where.append("COALESCE(status, 'active') = ?")
            params.append(status)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        rows = [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()

    if fmt == "csv":
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return buf.getvalue()
    return json.dumps(rows, ensure_ascii=False, indent=2)


def db_purge(db: str | None = None, older_than_days: int | None = None) -> int:
    """Remove old jobs. Without `older_than_days`, clears the whole database."""
    conn = _connect(db)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()
        if older_than_days and older_than_days > 0:
            cutoff = (datetime.now() - timedelta(days=older_than_days)).isoformat(timespec="seconds")
            cur.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff,))
        else:
            cur.execute("DELETE FROM jobs")
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted


def record_run(db: str | None = None, kind: str = "search", *,
               scope: str | None = None, targets: int = 0, fetched: int = 0,
               inserted: int = 0, errors: int = 0, status: str = "ok",
               details: dict | None = None, started_at: str | None = None) -> int:
    """
    Append an ingest run to the ``runs`` table and return its id.

    ``kind`` is ``search`` or ``ats``; ``status`` is ``ok``, ``partial`` or
    ``failed``. ``details`` is stored as JSON.
    """
    now = datetime.now().isoformat(timespec="seconds")
    conn = _connect(db)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO runs (
                kind, scope, targets, fetched, inserted, errors, status,
                details, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kind,
                scope,
                targets,
                fetched,
                inserted,
                errors,
                status,
                json.dumps(details, ensure_ascii=False) if details else None,
                started_at or now,
                now,
            ),
        )
        run_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return run_id


def db_runs(db: str | None = None, limit: int = 20) -> list[dict]:
    """Return the most recent ingest runs, newest first."""
    conn = _connect(db)
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (max(1, limit),)
        ).fetchall()
    finally:
        conn.close()
    runs: list[dict] = []
    for row in rows:
        item = dict(row)
        if item.get("details"):
            try:
                item["details"] = json.loads(item["details"])
            except (TypeError, ValueError):
                pass
        runs.append(item)
    return runs


def mark_stale(db: str | None = None, older_than_days: int = 30,
               source: str | None = None) -> int:
    """
    Mark ``active`` jobs not seen in ``older_than_days`` as ``stale``.

    ATS APIs only return open postings, so a long absence usually means the
    posting is gone. Optionally restrict to a single ``source`` (provider).
    """
    now = datetime.now()
    cutoff = (now - timedelta(days=older_than_days)).isoformat(timespec="seconds")
    sql = (
        "UPDATE jobs SET status = 'stale', status_changed_at = ? "
        "WHERE status = 'active' AND COALESCE(last_seen_at, created_at) < ?"
    )
    params: list = [now.isoformat(timespec="seconds"), cutoff]
    if source:
        sql += " AND COALESCE(source, domain) = ?"
        params.append(source)

    conn = _connect(db)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()
        cur.execute(sql, params)
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed


def mark_closed(db: str | None = None, older_than_days: int = 7,
                source: str | None = None) -> int:
    """
    Mark jobs that have been ``stale`` for ``older_than_days`` as ``closed``.

    ``older_than_days`` is measured from when the job became stale
    (``status_changed_at``). Optionally restrict to a single ``source``.
    """
    now = datetime.now()
    cutoff = (now - timedelta(days=older_than_days)).isoformat(timespec="seconds")
    sql = (
        "UPDATE jobs SET status = 'closed', status_changed_at = ? "
        "WHERE status = 'stale' AND "
        "COALESCE(status_changed_at, last_seen_at, created_at) < ?"
    )
    params: list = [now.isoformat(timespec="seconds"), cutoff]
    if source:
        sql += " AND COALESCE(source, domain) = ?"
        params.append(source)

    conn = _connect(db)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()
        cur.execute(sql, params)
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed
