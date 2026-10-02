#!/usr/bin/env python3
"""Testes automatizados para o jobsearch."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Adiciona o diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jobsearch.cli import (
    COUNTRIES,
    ATS,
    BOARDS,
    BACKENDS,
    country_term,
    domains_for,
    plan_queries,
    filter_jobs,
    default_basename,
    save_json,
    save_xlsx,
    search_ddg,
    search_google,
    SearchError,
)


class TestCountryTerm(unittest.TestCase):
    """Testes para country_term()."""

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
    """Testes para domains_for()."""

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
        self.assertNotIn("gupy.io", result)  # extra só vai para boards/all


class TestPlanQueries(unittest.TestCase):
    """Testes para plan_queries()."""

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
    """Testes para filter_jobs()."""

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
    """Testes para default_basename()."""

    def test_simple_role(self):
        result = default_basename("backend engineer")
        self.assertTrue(result.startswith("vagas_backend-engineer_"))

    def test_role_with_special_chars(self):
        result = default_basename("backend/engineer (senior)")
        self.assertTrue(result.startswith("vagas_backend-engineer-senior_"))

    def test_empty_role(self):
        result = default_basename("")
        self.assertTrue(result.startswith("vagas_vagas_"))


class TestSaveJson(unittest.TestCase):
    """Testes para save_json()."""

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            meta = {"role": "test", "scope": "geral"}
            jobs = [{"title": "Job 1", "link": "http://1"}]

            save_json(path, meta, jobs)

            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["role"], "test")
            self.assertEqual(data["total"], 1)
            self.assertEqual(len(data["jobs"]), 1)


class TestSaveXlsx(unittest.TestCase):
    """Testes para save_xlsx()."""

    def test_save_xlsx(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.xlsx")
            meta = {"role": "test", "scope": "geral"}
            jobs = [{"title": "Job 1", "link": "http://1", "domain": "test.com",
                     "location": "remote", "query": "test"}]

            result = save_xlsx(path, meta, jobs)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(path))


class TestSearchDdg(unittest.TestCase):
    """Testes para search_ddg()."""

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
    """Testes para search_google()."""

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
    """Testes para configuração de países."""

    def test_all_countries_have_required_keys(self):
        required_keys = ["names", "region", "gl", "indeed", "extra"]
        for code, config in COUNTRIES.items():
            for key in required_keys:
                self.assertIn(key, config, f"Country {code} missing key {key}")

    def test_country_count(self):
        self.assertEqual(len(COUNTRIES), 11)


if __name__ == "__main__":
    unittest.main()
