"""Tests for structured logging (JsonFormatter) and run metrics."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import tempfile
import time
import unittest
from io import StringIO
from unittest.mock import patch

from findmyjob.console import JsonFormatter, log, setup_logging
from findmyjob.metrics import run_summary, write_metrics


class TestJsonFormatter(unittest.TestCase):
    def test_standard_fields_and_extra(self):
        record = logging.LogRecord("findmyjob", logging.INFO, __file__, 1,
                                   "hello %s", ("world",), None)
        record.status = "ok"
        record.targets = 3
        out = json.loads(JsonFormatter().format(record))
        self.assertEqual(out["message"], "hello world")
        self.assertEqual(out["level"], "INFO")
        self.assertEqual(out["logger"], "findmyjob")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["targets"], 3)

    def test_exception_is_serialized(self):
        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.LogRecord("findmyjob", logging.ERROR, __file__, 1,
                                       "failed", (), sys.exc_info())
        out = json.loads(JsonFormatter().format(record))
        self.assertIn("boom", out["exception"])

    def test_extra_fields_survive_a_handler(self):
        setup_logging(json_format=True)
        self.addCleanup(setup_logging)
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        log.addHandler(handler)
        try:
            log.info("run summary", extra={"kind": "ats", "targets": 2})
        finally:
            log.removeHandler(handler)
        out = json.loads(stream.getvalue().strip())
        self.assertEqual(out["message"], "run summary")
        self.assertEqual(out["kind"], "ats")
        self.assertEqual(out["targets"], 2)


class TestSetupLogging(unittest.TestCase):
    def tearDown(self):
        setup_logging()  # restore the default plain formatter

    def test_json_format_installs_json_formatter(self):
        setup_logging(json_format=True)
        self.assertTrue(any(isinstance(h.formatter, JsonFormatter)
                            for h in log.handlers))

    def test_default_is_not_json(self):
        setup_logging()
        self.assertFalse(any(isinstance(h.formatter, JsonFormatter)
                             for h in log.handlers))


class TestMetricsHelpers(unittest.TestCase):
    def test_run_summary_adds_duration(self):
        summary = run_summary(started=time.monotonic(), kind="ats", targets=2)
        self.assertEqual(summary["kind"], "ats")
        self.assertEqual(summary["targets"], 2)
        self.assertGreaterEqual(summary["duration_s"], 0)

    def test_write_metrics_round_trips(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = os.path.join(tmp, "m.json")
        write_metrics(path, {"status": "ok", "fetched": 5})
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"status": "ok", "fetched": 5})


class TestMetricsCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(setup_logging)

    def test_ats_fetch_writes_metrics_file(self):
        import findmyjob.cli as cli

        targets = os.path.join(self.tmp, "companies.json")
        with open(targets, "w", encoding="utf-8") as fh:
            json.dump({"greenhouse": ["acme"]}, fh)
        metrics = os.path.join(self.tmp, "metrics.json")

        with patch.object(cli, "fetch_targets", return_value=([], [])), \
                patch("sys.stdout", new=StringIO()):
            rc = cli.ats_command(["fetch", "-t", targets, "--no-json",
                                  "--no-xlsx", "--metrics-file", metrics, "-q"])
        self.assertEqual(rc, 0)
        with open(metrics, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["kind"], "ats")
        self.assertEqual(data["targets"], 1)
        self.assertEqual(data["inserted"], 0)
        self.assertEqual(data["status"], "ok")
        self.assertIn("duration_s", data)

    def test_search_writes_metrics_file(self):
        import findmyjob.cli as cli

        metrics = os.path.join(self.tmp, "metrics.json")
        with patch.object(cli, "search_ddg", return_value=[]), \
                patch.object(cli, "BACKENDS", {"ddg": cli.search_ddg}), \
                patch("sys.stdout", new=StringIO()):
            rc = cli.main(["dev", "--metrics-file", metrics, "--no-json",
                           "--no-xlsx", "--delay", "0", "-m", "1", "-q"])
        self.assertEqual(rc, 0)
        with open(metrics, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["kind"], "search")
        self.assertEqual(data["backend"], "ddg")
        self.assertIn("duration_s", data)


if __name__ == "__main__":
    unittest.main()
