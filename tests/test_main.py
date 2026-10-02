#!/usr/bin/env python3
"""Automated tests for findmyjob."""

import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from findmyjob.cli import (
    ATS,
    BOARDS,
    COUNTRIES,
    SearchError,
    __version__,
    country_term,
    db_command,
    db_export,
    db_purge,
    db_stats,
    default_basename,
    domains_for,
    extract_company,
    filter_jobs,
    main,
    normalize_url,
    parse_posted_date,
    plan_queries,
    save_csv,
    save_json,
    save_to_db,
    save_xlsx,
    search_ddg,
    search_google,
)


class TestCountryTerm(unittest.TestCase):
    """Tests for country_term()."""

    def test_single_name(self):
        country = {"names": ["Portugal"]}
        self.assertEqual(country_term(country), '"Portugal"')

    def test_multiple_names(self):
        country = {"names": ["Brazil", "Brasil"]}
        self.assertEqual(country_term(country), '("Brazil" OR "Brasil")')

    def test_us_names(self):
        country = {"names": ["United States", "USA"]}
        self.assertEqual(country_term(country), '("United States" OR "USA")')


class TestDomainsFor(unittest.TestCase):
    """Tests for domains_for()."""

    def test_boards_no_country(self):
        result = domains_for("boards", None)
        self.assertEqual(result, BOARDS)

    def test_ats_no_country(self):
        result = domains_for("ats", None)
        self.assertEqual(result, ATS)

    def test_all_no_country(self):
        result = domains_for("all", None)
        self.assertEqual(result, BOARDS + ATS)

    def test_boards_with_country(self):
        country = COUNTRIES["br"]
        result = domains_for("boards", country)
        self.assertIn("br.indeed.com", result)
        self.assertIn("glassdoor.com.br", result)
        self.assertIn("gupy.io", result)
        self.assertIn("linkedin.com/jobs", result)

    def test_ats_with_country_no_extra(self):
        country = COUNTRIES["br"]
        result = domains_for("ats", country)
        self.assertIn("boards.greenhouse.io", result)
        self.assertNotIn("gupy.io", result)  # extra only goes to boards/all


class TestPlanQueries(unittest.TestCase):
    """Tests for plan_queries()."""

    def test_basic_query(self):
        plan = plan_queries("backend engineer", ["remote"], "boards", None)
        self.assertTrue(len(plan) > 0)
        for item in plan:
            self.assertIn("domain", item)
            self.assertIn("location", item)
            self.assertIn("query", item)
            self.assertIn("site:", item["query"])
            self.assertIn("backend engineer", item["query"])

    def test_with_country(self):
        country = COUNTRIES["br"]
        plan = plan_queries("developer", ["remote"], "boards", country)
        self.assertTrue(len(plan) > 0)
        for item in plan:
            self.assertIn("Brazil", item["query"])

    def test_multiple_locations(self):
        plan = plan_queries("developer", ["remote", "latam"], "boards", None)
        locations = [item["location"] for item in plan]
        self.assertIn("remote", locations)
        self.assertIn("latam", locations)

    def test_empty_locations_defaults(self):
        plan = plan_queries("developer", [], "boards", None)
        for item in plan:
            self.assertEqual(item["location"], "remote")


class TestFilterJobs(unittest.TestCase):
    """Tests for filter_jobs()."""

    def setUp(self):
        self.jobs = [
            {"title": "Senior Backend Python Developer", "link": "http://1"},
            {"title": "Junior Frontend Developer", "link": "http://2"},
            {"title": "Backend Go Engineer", "link": "http://3"},
            {"title": "Full Stack Python Developer", "link": "http://4"},
        ]

    def test_filter_include_keywords(self):
        result = filter_jobs(self.jobs, keywords=["Backend"])
        self.assertEqual(len(result), 2)
        self.assertNotIn(self.jobs[1], result)
        self.assertNotIn(self.jobs[3], result)

    def test_filter_exclude_keywords(self):
        result = filter_jobs(self.jobs, exclude_keywords=["junior"])
        self.assertEqual(len(result), 3)
        self.assertNotIn(self.jobs[1], result)

    def test_filter_include_and_exclude(self):
        result = filter_jobs(self.jobs, keywords=["python"], exclude_keywords=["junior"])
        self.assertEqual(len(result), 2)

    def test_no_filters(self):
        result = filter_jobs(self.jobs)
        self.assertEqual(len(result), 4)

    def test_empty_result(self):
        result = filter_jobs(self.jobs, keywords=["nonexistent"])
        self.assertEqual(len(result), 0)


class TestDefaultBasename(unittest.TestCase):
    """Tests for default_basename()."""

    def test_simple_role(self):
        result = default_basename("backend engineer")
        self.assertTrue(result.startswith("jobs_backend-engineer_"))

    def test_role_with_special_chars(self):
        result = default_basename("backend/engineer (senior)")
        self.assertTrue(result.startswith("jobs_backend-engineer-senior_"))

    def test_empty_role(self):
        result = default_basename("")
        self.assertTrue(result.startswith("jobs_jobs_"))


class TestSaveJson(unittest.TestCase):
    """Tests for save_json()."""

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            meta = {"role": "test", "scope": "general"}
            jobs = [{"title": "Job 1", "link": "http://1"}]

            save_json(path, meta, jobs)

            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["role"], "test")
            self.assertEqual(data["total"], 1)
            self.assertEqual(len(data["jobs"]), 1)


class TestSaveXlsx(unittest.TestCase):
    """Tests for save_xlsx()."""

    def test_save_xlsx(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.xlsx")
            meta = {"role": "test", "scope": "general"}
            jobs = [{"title": "Job 1", "link": "http://1", "domain": "test.com",
                     "location": "remote", "query": "test"}]

            result = save_xlsx(path, meta, jobs)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(path))


class TestSearchDdg(unittest.TestCase):
    """Tests for search_ddg()."""

    @patch("ddgs.DDGS")
    def test_successful_search(self, mock_ddg_class):
        mock_ddg = MagicMock()
        mock_ddg_class.return_value = mock_ddg
        mock_ddg.text.return_value = [
            {"title": "Job 1", "href": "http://1"},
            {"title": "Job 2", "href": "http://2"},
        ]

        result = search_ddg("test query", 10, None)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "Job 1")

    @patch("ddgs.DDGS")
    def test_retry_on_failure(self, mock_ddg_class):
        mock_ddg = MagicMock()
        mock_ddg_class.return_value = mock_ddg
        mock_ddg.text.side_effect = [Exception("Network error"), [
            {"title": "Job 1", "href": "http://1"},
        ]]

        result = search_ddg("test query", 10, None, retries=2, backoff=0.1)
        self.assertEqual(len(result), 1)

    @patch("ddgs.DDGS")
    def test_all_retries_fail(self, mock_ddg_class):
        mock_ddg = MagicMock()
        mock_ddg_class.return_value = mock_ddg
        mock_ddg.text.side_effect = Exception("Network error")

        with self.assertRaises(SearchError):
            search_ddg("test query", 10, None, retries=2, backoff=0.1)


class TestSearchGoogle(unittest.TestCase):
    """Tests for search_google()."""

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key", "GOOGLE_CX": "test_cx"})
    @patch("requests.get")
    def test_successful_search(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {"title": "Job 1", "link": "http://1"},
                {"title": "Job 2", "link": "http://2"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = search_google("test query", 10, None)
        self.assertEqual(len(result), 2)

    def test_missing_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SearchError):
                search_google("test query", 10, None)


class TestCountries(unittest.TestCase):
    """Tests for the country configuration."""

    def test_all_countries_have_required_keys(self):
        required_keys = ["names", "region", "gl", "indeed", "extra"]
        for code, config in COUNTRIES.items():
            for key in required_keys:
                self.assertIn(key, config, f"Country {code} missing key {key}")

    def test_country_count(self):
        self.assertEqual(len(COUNTRIES), 11)


class TestParsePostedDate(unittest.TestCase):
    """Tests for parse_posted_date()."""

    def setUp(self):
        from datetime import datetime
        self.now = datetime(2026, 10, 2, 12, 0, 0)

    def test_relative_days(self):
        dt = parse_posted_date("2 days ago", now=self.now)
        self.assertEqual(dt.date().isoformat(), "2026-09-30")

    def test_relative_portuguese(self):
        dt = parse_posted_date("há 3 dias", now=self.now)
        self.assertEqual(dt.date().isoformat(), "2026-09-29")

    def test_today_and_yesterday(self):
        self.assertEqual(parse_posted_date("today", now=self.now), self.now)
        self.assertEqual(parse_posted_date("ontem", now=self.now).date().isoformat(),
                         "2026-10-01")

    def test_numeric_days(self):
        self.assertEqual(parse_posted_date(5, now=self.now).date().isoformat(),
                         "2026-09-27")

    def test_iso(self):
        self.assertEqual(parse_posted_date("2026-09-28", now=self.now).date().isoformat(),
                         "2026-09-28")

    def test_unknown(self):
        self.assertIsNone(parse_posted_date("no date", now=self.now))
        self.assertIsNone(parse_posted_date(None, now=self.now))


class TestExtractCompany(unittest.TestCase):
    """Tests for extract_company()."""

    def test_ats_urls(self):
        self.assertEqual(extract_company("https://jobs.lever.co/acme-corp/1"), "Acme Corp")
        self.assertEqual(extract_company("https://boards.greenhouse.io/stripe/jobs/1"), "Stripe")
        self.assertEqual(extract_company("https://apply.workable.com/remotebase/j/1"), "Remotebase")
        self.assertEqual(extract_company("https://jobs.ashbyhq.com/scalera/x"), "Scalera")

    def test_subdomain_ats(self):
        self.assertEqual(extract_company("https://acme.gupy.io/jobs/1"), "Acme")
        self.assertEqual(
            extract_company("https://acme.wd3.myworkdayjobs.com/en-US/careers/job/1"), "Acme")

    def test_from_title(self):
        self.assertEqual(extract_company("", "Senior Backend Engineer at Nubank"), "Nubank")
        self.assertEqual(extract_company("", "Python Developer - Acme Corp"), "Acme Corp")

    def test_unknown(self):
        self.assertEqual(extract_company("https://www.linkedin.com/jobs/view/123", "Any"), "")


class TestSaveCsv(unittest.TestCase):
    """Tests for save_csv()."""

    def test_writes_expected_columns(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "out.csv")
            jobs = [{"title": "Dev", "company": "Acme", "link": "https://x/1",
                     "domain": "x.com", "location": "remote", "query": "q",
                     "posted_at": "2026-10-01", "description": "desc"}]
            self.assertTrue(save_csv(path, jobs))
            content = Path(path).read_text(encoding="utf-8-sig")
            header = content.splitlines()[0]
            self.assertIn("company", header)
            self.assertIn("Acme", content)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


class TestNormalizeUrl(unittest.TestCase):
    """Tests for normalize_url()."""

    def test_removes_tracking(self):
        url = "HTTPS://Example.com/job/1/?utm_source=x&gclid=abc&a=1#frag"
        self.assertEqual(normalize_url(url), "https://example.com/job/1?a=1")

    def test_empty(self):
        self.assertEqual(normalize_url(""), "")


class TestFilterJobsDates(unittest.TestCase):
    """Tests for the date filter."""

    def _jobs(self):
        from datetime import datetime, timedelta
        now = datetime.now()
        return [
            {"title": "recent", "link": "1",
             "posted_at": (now - timedelta(days=1)).isoformat()},
            {"title": "old", "link": "2",
             "posted_at": (now - timedelta(days=30)).isoformat()},
            {"title": "snippet", "link": "3", "snippet": "posted 2 days ago"},
            {"title": "no date", "link": "4"},
        ]

    def test_max_days_keeps_unknown(self):
        result = filter_jobs(self._jobs(), max_days=3)
        titles = {j["title"] for j in result}
        self.assertEqual(titles, {"recent", "snippet", "no date"})

    def test_max_days_strict(self):
        result = filter_jobs(self._jobs(), max_days=3, keep_unknown_dates=False)
        titles = {j["title"] for j in result}
        self.assertEqual(titles, {"recent", "snippet"})

    def test_max_days_zero_disables(self):
        self.assertEqual(len(filter_jobs(self._jobs(), max_days=0)), 4)

    def test_min_and_max_date(self):
        from datetime import datetime, timedelta
        now = datetime.now()
        jobs = [
            {"title": "target", "link": "1", "posted_at": now.isoformat()},
            {"title": "old", "link": "2",
             "posted_at": (now - timedelta(days=40)).isoformat()},
            {"title": "no date", "link": "3"},
        ]
        lo = (now - timedelta(days=5)).strftime("%Y-%m-%d")
        hi = now.strftime("%Y-%m-%d")
        result = filter_jobs(jobs, min_date=lo, max_date=hi)
        self.assertEqual({j["title"] for j in result}, {"target", "no date"})
        strict = filter_jobs(jobs, min_date=lo, max_date=hi, keep_unknown_dates=False)
        self.assertEqual({j["title"] for j in strict}, {"target"})


class TestDatabase(unittest.TestCase):
    """Tests for SQLite persistence."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_and_dedupe(self):
        jobs = [
            {"title": "A", "link": "https://x.com/1?utm_source=a"},
            {"title": "B", "link": "https://x.com/2"},
            {"title": "C", "link": "https://x.com/1"},
        ]
        self.assertEqual(save_to_db(jobs, self.db), 2)
        self.assertEqual(save_to_db(jobs, self.db), 0)
        self.assertEqual(db_stats(self.db)["total"], 2)

    def test_export_json_and_csv(self):
        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        self.assertEqual(json.loads(db_export(self.db, fmt="json"))[0]["title"], "A")
        self.assertIn("title", db_export(self.db, fmt="csv").splitlines()[0])

    def test_purge(self):
        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        self.assertEqual(db_purge(self.db), 1)
        self.assertEqual(db_stats(self.db)["total"], 0)

    def test_persists_provider_and_external_id(self):
        save_to_db([{"title": "A", "link": "https://x.com/1",
                     "provider": "greenhouse", "external_id": "42"}], self.db)
        row = json.loads(db_export(self.db, fmt="json"))[0]
        self.assertEqual(row["provider"], "greenhouse")
        self.assertEqual(row["external_id"], "42")

    def test_backfills_identity_on_existing_row(self):
        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        # A later run that knows the identity should backfill it.
        save_to_db([{"title": "A", "link": "https://x.com/1",
                     "provider": "lever", "external_id": "9"}], self.db)
        row = json.loads(db_export(self.db, fmt="json"))[0]
        self.assertEqual(row["provider"], "lever")
        self.assertEqual(row["external_id"], "9")

    def test_db_command_stats(self):
        save_to_db([{"title": "A", "link": "https://x.com/1"}], self.db)
        with patch("sys.stdout", new=StringIO()) as out:
            rc = db_command(["--db", self.db, "stats"])
        self.assertEqual(rc, 0)
        self.assertIn("Total jobs", out.getvalue())


class TestMainCli(unittest.TestCase):
    """Tests for the entry point."""

    def test_show_queries_returns_zero(self):
        with patch("sys.stdout", new=StringIO()):
            rc = main(["backend engineer", "--show-queries", "-c", "br"])
        self.assertEqual(rc, 0)

    def test_list_countries_returns_zero(self):
        with patch("sys.stdout", new=StringIO()):
            rc = main(["--list-countries"])
        self.assertEqual(rc, 0)

    def test_db_dispatch(self):
        tmp = tempfile.mkdtemp()
        try:
            save_to_db([{"title": "A", "link": "https://x.com/1"}],
                       os.path.join(tmp, "t.db"))
            with patch("sys.stdout", new=StringIO()) as out:
                rc = main(["db", "--db", os.path.join(tmp, "t.db"), "stats"])
            self.assertEqual(rc, 0)
            self.assertIn("Total jobs", out.getvalue())
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_version_flag(self):
        for argv in (["--version"], ["-V"], ["ats", "--version"],
                     ["db", "--version"]):
            with self.subTest(argv=argv):
                with patch("sys.stdout", new=StringIO()) as out:
                    with self.assertRaises(SystemExit) as cm:
                        main(argv)
                self.assertEqual(cm.exception.code, 0)
                self.assertEqual(out.getvalue().strip(),
                                 f"findmyjob {__version__}")


if __name__ == "__main__":
    unittest.main()
