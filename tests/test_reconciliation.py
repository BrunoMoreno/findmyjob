"""Tests for job lifecycle reconciliation and ingest run records."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

from findmyjob.cli import db_command
from findmyjob.db import (
    db_export,
    db_runs,
    db_stats,
    mark_closed,
    mark_stale,
    record_run,
    save_to_db,
)
from findmyjob.dedup import normalize_url


def _status(db, link):
    rows = json.loads(db_export(db, fmt="json"))
    for row in rows:
        if row["link_key"] == normalize_url(link):
            return row["status"]
    raise AssertionError(f"job not found: {link}")


def _backdate(db, link, *, seen_days=0, status_days=0):
    """Move a job's lifecycle timestamps into the past."""
    now = datetime.now()
    conn = sqlite3.connect(db)
    key = normalize_url(link)
    if seen_days:
        conn.execute("UPDATE jobs SET last_seen_at=? WHERE link_key=?",
                     ((now - timedelta(days=seen_days)).isoformat(timespec="seconds"), key))
    if status_days:
        conn.execute("UPDATE jobs SET status_changed_at=? WHERE link_key=?",
                     ((now - timedelta(days=status_days)).isoformat(timespec="seconds"), key))
    conn.commit()
    conn.close()


class _DbTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestJobLifecycle(_DbTestCase):
    def test_new_jobs_start_active(self):
        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        self.assertEqual(_status(self.db, "https://x.com/1"), "active")
        self.assertEqual(dict(db_stats(self.db)["by_status"]), {"active": 1})

    def test_export_can_filter_by_status(self):
        save_to_db([
            {"title": "old", "link": "https://x.com/old"},
            {"title": "new", "link": "https://x.com/new"},
        ], self.db)
        _backdate(self.db, "https://x.com/old", seen_days=30)
        mark_stale(self.db, 7)
        active = json.loads(db_export(self.db, status="active"))
        self.assertEqual([r["title"] for r in active], ["new"])
        stale = json.loads(db_export(self.db, status="stale"))
        self.assertEqual([r["title"] for r in stale], ["old"])

    def test_mark_stale_only_touches_old_active_jobs(self):
        save_to_db([
            {"title": "old", "link": "https://x.com/old"},
            {"title": "fresh", "link": "https://x.com/fresh"},
        ], self.db)
        _backdate(self.db, "https://x.com/old", seen_days=30)

        self.assertEqual(mark_stale(self.db, 7), 1)
        self.assertEqual(_status(self.db, "https://x.com/old"), "stale")
        self.assertEqual(_status(self.db, "https://x.com/fresh"), "active")
        # Idempotent: already stale jobs are not touched again.
        self.assertEqual(mark_stale(self.db, 7), 0)

    def test_mark_stale_can_be_scoped_to_source(self):
        save_to_db([
            {"title": "gh", "link": "https://x.com/1", "source": "greenhouse"},
            {"title": "lv", "link": "https://x.com/2", "source": "lever"},
        ], self.db)
        _backdate(self.db, "https://x.com/1", seen_days=30)
        _backdate(self.db, "https://x.com/2", seen_days=30)

        self.assertEqual(mark_stale(self.db, 7, source="greenhouse"), 1)
        self.assertEqual(_status(self.db, "https://x.com/1"), "stale")
        self.assertEqual(_status(self.db, "https://x.com/2"), "active")

    def test_mark_closed_requires_the_job_to_be_stale(self):
        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        # Still active: closing does not skip the stale step.
        self.assertEqual(mark_closed(self.db, 0), 0)

        _backdate(self.db, "https://x.com/1", seen_days=1)
        mark_stale(self.db, 0)
        self.assertEqual(_status(self.db, "https://x.com/1"), "stale")
        _backdate(self.db, "https://x.com/1", status_days=30)
        self.assertEqual(mark_closed(self.db, 7), 1)
        self.assertEqual(_status(self.db, "https://x.com/1"), "closed")

    def test_reappearing_job_reactivates(self):
        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        _backdate(self.db, "https://x.com/1", seen_days=1)
        mark_stale(self.db, 0)
        self.assertEqual(_status(self.db, "https://x.com/1"), "stale")

        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        self.assertEqual(_status(self.db, "https://x.com/1"), "active")


class TestRunRecords(_DbTestCase):
    def test_record_and_list_runs(self):
        run_id = record_run(self.db, "ats", scope="companies.json", targets=3,
                            fetched=10, inserted=4, errors=1, status="partial",
                            details={"providers": ["greenhouse"]})
        self.assertIsInstance(run_id, int)

        runs = db_runs(self.db)
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run["kind"], "ats")
        self.assertEqual(run["status"], "partial")
        self.assertEqual(run["fetched"], 10)
        self.assertEqual(run["inserted"], 4)
        self.assertEqual(run["details"], {"providers": ["greenhouse"]})

    def test_empty_database_has_no_runs(self):
        self.assertEqual(db_runs(self.db), [])


class TestDbCommandReconciliation(_DbTestCase):
    def test_runs_command_json(self):
        record_run(self.db, "search", scope="general", targets=2, fetched=5,
                   inserted=1)
        with patch("sys.stdout", new=StringIO()) as out:
            rc = db_command(["--db", self.db, "runs", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())[0]["kind"], "search")

    def test_mark_stale_command(self):
        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        _backdate(self.db, "https://x.com/1", seen_days=30)
        with patch("sys.stdout", new=StringIO()) as out:
            rc = db_command(["--db", self.db, "mark-stale",
                             "--older-than", "7", "-y"])
        self.assertEqual(rc, 0)
        self.assertIn("1 job(s) marked as stale", out.getvalue())
        self.assertEqual(_status(self.db, "https://x.com/1"), "stale")

    def test_mark_closed_command(self):
        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        _backdate(self.db, "https://x.com/1", seen_days=1)
        mark_stale(self.db, 0)
        _backdate(self.db, "https://x.com/1", status_days=30)
        with patch("sys.stdout", new=StringIO()) as out:
            rc = db_command(["--db", self.db, "mark-closed",
                             "--older-than", "7", "-y"])
        self.assertEqual(rc, 0)
        self.assertIn("1 job(s) marked as closed", out.getvalue())
        self.assertEqual(_status(self.db, "https://x.com/1"), "closed")

    def test_cancelled_without_yes(self):
        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        _backdate(self.db, "https://x.com/1", seen_days=30)
        with patch("builtins.input", return_value="n"), \
                patch("sys.stdout", new=StringIO()) as out:
            rc = db_command(["--db", self.db, "mark-stale", "--older-than", "7"])
        self.assertEqual(rc, 1)
        self.assertIn("Cancelled", out.getvalue())
        self.assertEqual(_status(self.db, "https://x.com/1"), "active")


class TestAtsRunRecord(_DbTestCase):
    def test_ats_fetch_records_a_run(self):
        import findmyjob.cli as cli

        targets = os.path.join(self.tmp, "companies.json")
        with open(targets, "w", encoding="utf-8") as fh:
            json.dump({"greenhouse": ["acme"]}, fh)

        found = [{"title": "A", "link": "https://x.com/1", "source": "greenhouse"}]
        with patch.object(cli, "fetch_targets", return_value=(found, [])), \
                patch("sys.stdout", new=StringIO()):
            rc = cli.ats_command(["fetch", "-t", targets, "--db", self.db,
                                  "--no-json", "--no-xlsx", "-q"])
        self.assertEqual(rc, 0)

        runs = db_runs(self.db)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["kind"], "ats")
        self.assertEqual(runs[0]["targets"], 1)
        self.assertEqual(runs[0]["fetched"], 1)
        self.assertEqual(runs[0]["inserted"], 1)
        self.assertEqual(runs[0]["status"], "ok")
        self.assertEqual(_status(self.db, "https://x.com/1"), "active")


if __name__ == "__main__":
    unittest.main()
