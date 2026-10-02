"""Tests for the ATS JSON APIs, discovery, and data-quality fixes."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from findmyjob import console
from findmyjob.ats import (
    AtsError,
    fetch_ashby,
    fetch_greenhouse,
    fetch_lever,
    fetch_smartrecruiters,
    fetch_targets,
    load_targets,
)
from findmyjob.cli import _dedup_normalized, init_db
from findmyjob.dedup import normalize_url
from findmyjob.discover import extract_ats_target, extract_ats_targets, save_targets
from findmyjob.enrich import extract_company
from findmyjob.search import _retry_notice

GREENHOUSE = {"jobs": [{
    "title": "Backend Engineer",
    "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
    "location": {"name": "Remote"},
    "first_published": "2026-01-02T03:04:05-05:00",
    "content": "<p>Hi <b>there</b>&nbsp;!</p>",
}]}

LEVER = [{
    "text": "Platform Engineer",
    "hostedUrl": "https://jobs.lever.co/acme/abc",
    "categories": {"location": "Berlin"},
    "createdAt": 1700000000000,
    "descriptionPlain": "A role",
}]

ASHBY = {"jobs": [{
    "title": "Data Engineer",
    "jobUrl": "https://jobs.ashbyhq.com/acme/xyz",
    "location": "NYC",
    "publishedAt": "2026-02-03T00:00:00.000Z",
    "descriptionHtml": "<p>x</p>",
    "isListed": True,
}, {
    "title": "Hidden",
    "jobUrl": "https://jobs.ashbyhq.com/acme/hidden",
    "isListed": False,
}]}

SMARTRECRUITERS = {"content": [{
    "id": "123",
    "name": "Chef",
    "releasedDate": "2026-03-04T00:00:00.000Z",
    "location": {"city": "Paris", "region": "IDF", "country": "fr"},
    "ref": "https://api.smartrecruiters.com/v1/companies/acme/postings/123",
}]}


class TestAtsProviders(unittest.TestCase):
    def test_greenhouse(self):
        with patch("findmyjob.ats._http_json", return_value=GREENHOUSE):
            jobs = fetch_greenhouse("acme")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Backend Engineer")
        self.assertEqual(jobs[0]["source"], "greenhouse")
        self.assertEqual(jobs[0]["company"], "Acme")
        self.assertIn("Hi there !", jobs[0]["description"])
        self.assertNotIn("<b>", jobs[0]["description"])

    def test_lever(self):
        with patch("findmyjob.ats._http_json", return_value=LEVER):
            jobs = fetch_lever("acme")
        self.assertEqual(jobs[0]["title"], "Platform Engineer")
        self.assertEqual(jobs[0]["location"], "Berlin")
        self.assertTrue(jobs[0]["posted_at"].startswith("2023-11-14"))

    def test_ashby_skips_unlisted(self):
        with patch("findmyjob.ats._http_json", return_value=ASHBY):
            jobs = fetch_ashby("acme")
        self.assertEqual([j["title"] for j in jobs], ["Data Engineer"])

    def test_smartrecruiters_builds_web_url(self):
        with patch("findmyjob.ats._http_json", return_value=SMARTRECRUITERS):
            jobs = fetch_smartrecruiters("acme")
        self.assertEqual(jobs[0]["link"], "https://jobs.smartrecruiters.com/acme/123")
        self.assertEqual(jobs[0]["location"], "Paris, IDF, fr")


class TestLoadTargets(unittest.TestCase):
    def _write(self, payload):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh)
        self.addCleanup(os.remove, path)
        return path

    def test_mapping(self):
        path = self._write({"greenhouse": ["a"], "lever": ["b", "c"]})
        self.assertEqual(load_targets(path),
                         {"greenhouse": ["a"], "lever": ["b", "c"]})

    def test_flat_list(self):
        path = self._write(["greenhouse/a", "lever/b"])
        self.assertEqual(load_targets(path), {"greenhouse": ["a"], "lever": ["b"]})

    def test_unknown_provider(self):
        path = self._write({"nope": ["a"]})
        with self.assertRaises(ValueError):
            load_targets(path)


class TestFetchTargets(unittest.TestCase):
    def test_collects_errors_without_aborting(self):
        def boom(slug, **kwargs):
            raise AtsError("nope")

        def ok(slug, **kwargs):
            return [{"title": "T", "link": "https://x/1"}]

        with patch.dict("findmyjob.ats.FETCHERS",
                        {"greenhouse": boom, "lever": ok}, clear=True), \
                patch.object(console, "QUIET", True):
            jobs, errors = fetch_targets({"greenhouse": ["a"], "lever": ["b"]})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("greenhouse/a", errors[0])


class TestDiscover(unittest.TestCase):
    def test_extract_each_provider(self):
        cases = {
            "https://jobs.lever.co/acme/123": ("lever", "acme"),
            "https://boards.greenhouse.io/stripe/jobs/9": ("greenhouse", "stripe"),
            "https://job-boards.greenhouse.io/stripe/jobs/9": ("greenhouse", "stripe"),
            "https://jobs.ashbyhq.com/openai/xyz": ("ashby", "openai"),
            "https://jobs.smartrecruiters.com/Accor/1": ("smartrecruiters", "accor"),
        }
        for link, expected in cases.items():
            self.assertEqual(extract_ats_target(link), expected)

    def test_extract_ignores_non_ats(self):
        self.assertIsNone(extract_ats_target("https://example.com/jobs/1"))

    def test_extract_groups_and_dedups(self):
        links = ["https://jobs.lever.co/acme/1", "https://jobs.lever.co/acme/2",
                 "https://boards.greenhouse.io/x/jobs/1"]
        self.assertEqual(extract_ats_targets(links),
                         {"lever": ["acme"], "greenhouse": ["x"]})

    def test_save_targets_merge(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump({"lever": ["a"]}, fh)
        self.addCleanup(os.remove, path)
        merged = save_targets(path, {"lever": ["b"], "ashby": ["c"]}, merge=True)
        self.assertEqual(merged, {"lever": ["a", "b"], "ashby": ["c"]})


class TestInitDb(unittest.TestCase):
    def test_creates_file_and_schema(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = os.path.join(tmp, "new.db")
        returned = init_db(path)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(returned, Path(path).resolve())
        conn = sqlite3.connect(path)
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
        self.assertIn("jobs", tables)

    def test_main_creates_db_even_without_jobs(self):
        import findmyjob.cli as cli

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.addCleanup(setattr, console, "QUIET", False)
        path = os.path.join(tmp, "empty.db")

        with patch.object(cli, "search_ddg", return_value=[]), \
                patch.object(cli, "BACKENDS", {"ddg": cli.search_ddg}):
            rc = cli.main(["dev", "--db", path, "--no-json", "--no-xlsx",
                           "--delay", "0", "-m", "1", "-q"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(path))


class TestDedupFix(unittest.TestCase):
    def test_lever_prefix_and_gh_src_removed(self):
        self.assertEqual(
            normalize_url("https://jobs.lever.co/acme/x?lever-source=LinkedIn"),
            "https://jobs.lever.co/acme/x")

    def test_gh_src_removed(self):
        self.assertEqual(
            normalize_url("https://x.com/job?gh_src=abc&a=1"),
            "https://x.com/job?a=1")

    def test_gh_jid_preserved(self):
        url = "https://stripe.com/jobs/search?gh_jid=8172487"
        self.assertEqual(normalize_url(url), url)

    def test_dedup_normalized_collapses_tracking_variants(self):
        jobs = [
            {"title": "A", "link": "https://x.com/j/1?utm_source=a"},
            {"title": "B", "link": "https://x.com/j/1?utm_source=b"},
            {"title": "C", "link": "https://x.com/j/2"},
        ]
        unique = _dedup_normalized(jobs)
        self.assertEqual([j["title"] for j in unique], ["A", "C"])


class TestExtractCompanyFix(unittest.TestCase):
    def test_ats_urls_still_work(self):
        self.assertEqual(extract_company("https://jobs.lever.co/acme-corp/1"), "Acme Corp")

    def test_rejects_location_and_seniority(self):
        self.assertEqual(extract_company("", "Backend Engineer - Remote"), "")
        self.assertEqual(extract_company("", "Senior Python Developer - São Paulo"), "")
        self.assertEqual(extract_company("", "Engenheiro de Software | Pleno"), "")

    def test_keeps_company_after_tech_segment(self):
        self.assertEqual(
            extract_company("", "Software Engineer - Python - Stone Pagamentos"),
            "Stone Pagamentos")

    def test_at_pattern(self):
        self.assertEqual(extract_company("", "Senior Backend Engineer at Nubank"), "Nubank")


class TestQuietRetries(unittest.TestCase):
    def test_quiet_suppresses_retry_notice(self):
        with patch.object(console, "QUIET", True), patch("builtins.print") as mock_print:
            _retry_notice(0, 3, Exception("x"), 1.0)
        mock_print.assert_not_called()

    def test_non_quiet_prints_retry_notice(self):
        with patch.object(console, "QUIET", False), patch("builtins.print") as mock_print:
            _retry_notice(0, 3, Exception("x"), 1.0)
        mock_print.assert_called_once()


if __name__ == "__main__":
    unittest.main()
