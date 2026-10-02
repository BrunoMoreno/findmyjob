"""Tests for concurrent ATS fetching (``fetch_targets``)."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from findmyjob import console
from findmyjob.ats import AtsError, _RateLimiter, fetch_targets


class _FakeClock:
    """Minimal stand-in for the ``time`` module used by the rate limiter."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _run(fetchers, targets, **kwargs):
    with patch.dict("findmyjob.ats.FETCHERS", fetchers, clear=True), \
            patch.object(console, "QUIET", True):
        return fetch_targets(targets, **kwargs)


class TestSequential(unittest.TestCase):
    def test_preserves_order_and_defaults(self):
        def fetcher(slug, **kwargs):
            return [{"title": slug, "link": f"https://x/{slug}"}]

        jobs, errors = _run({"greenhouse": fetcher},
                            {"greenhouse": ["a", "b", "c"]})
        self.assertEqual(errors, [])
        self.assertEqual([j["title"] for j in jobs], ["a", "b", "c"])


class TestConcurrent(unittest.TestCase):
    def test_preserves_target_order(self):
        def fetcher(slug, **kwargs):
            time.sleep(0.01)
            return [{"title": slug, "link": f"https://x/{slug}"}]

        jobs, errors = _run({"greenhouse": fetcher, "lever": fetcher},
                            {"greenhouse": ["a", "b"], "lever": ["c"]},
                            concurrency=3)
        self.assertEqual(errors, [])
        self.assertEqual([j["title"] for j in jobs], ["a", "b", "c"])

    def test_error_isolation(self):
        def boom(slug, **kwargs):
            raise AtsError("nope")

        def ok(slug, **kwargs):
            return [{"title": slug, "link": f"https://x/{slug}"}]

        jobs, errors = _run({"greenhouse": boom, "lever": ok},
                            {"greenhouse": ["a", "b"], "lever": ["c"]},
                            concurrency=3)
        self.assertEqual([j["title"] for j in jobs], ["c"])
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(e.startswith("greenhouse/") for e in errors))

    def test_unknown_provider_is_reported(self):
        jobs, errors = _run({"greenhouse": lambda slug, **kw: []},
                            {"greenhouse": ["a"], "nope": ["b"]},
                            concurrency=2)
        self.assertEqual(jobs, [])
        self.assertEqual(errors, ["nope: unknown provider"])

    def test_per_host_caps_same_host(self):
        state = {"current": 0, "peak": 0}
        lock = threading.Lock()

        def fetcher(slug, **kwargs):
            with lock:
                state["current"] += 1
                state["peak"] = max(state["peak"], state["current"])
            time.sleep(0.02)
            with lock:
                state["current"] -= 1
            return [{"title": slug, "link": f"https://x/{slug}"}]

        jobs, errors = _run({"greenhouse": fetcher},
                            {"greenhouse": ["a", "b", "c", "d"]},
                            concurrency=4, per_host=2)
        self.assertEqual(errors, [])
        self.assertEqual(len(jobs), 4)
        self.assertLessEqual(state["peak"], 2)

    def test_different_hosts_run_in_parallel(self):
        # per_host=1, but greenhouse and lever are different hosts, so both
        # requests must be able to run at the same time. A global (rather than
        # per-host) limit would deadlock the barrier and time out.
        barrier = threading.Barrier(2, timeout=2.0)
        overlapped = {"value": False}

        def fetcher(slug, **kwargs):
            try:
                barrier.wait()
                overlapped["value"] = True
            except threading.BrokenBarrierError:
                pass
            return []

        _run({"greenhouse": fetcher, "lever": fetcher},
             {"greenhouse": ["a"], "lever": ["b"]}, concurrency=2, per_host=1)
        self.assertTrue(overlapped["value"])


class TestRateLimiter(unittest.TestCase):
    def test_spaces_request_starts(self):
        clock = _FakeClock()
        with patch("findmyjob.ats.time", clock):
            limiter = _RateLimiter(2.0)
            limiter.wait()      # first start at t=0; next allowed at t=2
            clock.now = 0.5
            limiter.wait()      # has to wait 1.5s
        self.assertEqual(clock.sleeps, [1.5])

    def test_zero_delay_is_a_noop(self):
        clock = _FakeClock()
        with patch("findmyjob.ats.time", clock):
            limiter = _RateLimiter(0)
            limiter.wait()
            limiter.wait()
        self.assertEqual(clock.sleeps, [])


class TestCliWiring(unittest.TestCase):
    def test_fetch_passes_concurrency_flags(self):
        import findmyjob.cli as cli

        self.addCleanup(setattr, console, "QUIET", False)
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump({"greenhouse": ["a"]}, fh)
        self.addCleanup(os.remove, path)

        captured = {}

        def fake_fetch(targets, **kwargs):
            captured.update(kwargs)
            return [], []

        with patch.object(cli, "fetch_targets", side_effect=fake_fetch):
            rc = cli.ats_command(["fetch", "-t", path, "--no-json", "--no-xlsx",
                                  "--concurrency", "4", "--per-host", "2", "-q"])
        self.assertEqual(rc, 0)
        self.assertEqual(captured["concurrency"], 4)
        self.assertEqual(captured["per_host"], 2)


if __name__ == "__main__":
    unittest.main()
