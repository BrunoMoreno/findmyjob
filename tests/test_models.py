"""Tests for the canonical JobPosting model."""

from __future__ import annotations

import datetime as dt
import json

from findmyjob.models import JobPosting


class TestConstruction:
    def test_defaults(self):
        job = JobPosting(title="Dev", link="https://x/1")
        assert job.provider == ""
        assert job.external_id == ""
        assert job.location == ""
        assert job.posted_at is None

    def test_none_text_becomes_empty(self):
        job = JobPosting(title=None, link=None, company=None)
        assert job.title == ""
        assert job.link == ""
        assert job.company == ""

    def test_extra_keys_ignored(self):
        job = JobPosting(title="Dev", link="https://x/1", unknown="x")
        assert not hasattr(job, "unknown")

    def test_whitespace_stripped(self):
        job = JobPosting(title="  Dev  ", link="https://x/1")
        assert job.title == "Dev"


class TestPostedAt:
    def test_iso_with_timezone(self):
        job = JobPosting(title="Dev", link="x", posted_at="2026-01-02T03:04:05-05:00")
        assert job.posted_at is not None
        assert job.posted_at.utcoffset() == dt.timedelta(hours=-5)
        assert json.loads(json.dumps(job.to_dict()))["posted_at"].startswith(
            "2026-01-02T03:04:05")

    def test_iso_z_suffix(self):
        job = JobPosting(title="Dev", link="x", posted_at="2026-02-03T00:00:00.000Z")
        assert job.posted_at == dt.datetime(2026, 2, 3, tzinfo=dt.timezone.utc)

    def test_microseconds_removed(self):
        job = JobPosting(title="Dev", link="x", posted_at="2026-02-03T00:00:00.123456")
        assert job.posted_at == dt.datetime(2026, 2, 3, 0, 0, 0)

    def test_relative_text(self):
        job = JobPosting(title="Dev", link="x", posted_at="2 days ago")
        assert job.posted_at is not None
        assert (dt.datetime.now() - job.posted_at).days == 2

    def test_unparseable_is_none(self):
        job = JobPosting(title="Dev", link="x", posted_at="no date")
        assert job.posted_at is None


class TestHelpers:
    def test_link_key_strips_tracking(self):
        job = JobPosting(title="Dev", link="https://x.com/j/1?utm_source=a&a=1")
        assert job.link_key == "https://x.com/j/1?a=1"

    def test_to_dict_shape_is_json_serializable(self):
        job = JobPosting(title="Dev", link="x", posted_at="2026-01-02")
        data = job.to_dict()
        json.dumps(data)  # must not raise
        assert set(data) == {
            "title", "link", "company", "location", "description", "snippet",
            "domain", "source", "query", "provider", "external_id", "posted_at",
        }

    def test_from_raw_derives_company_from_link(self):
        job = JobPosting.from_raw(
            {"title": "Backend", "link": "https://jobs.lever.co/acme/1"})
        assert job.company == "Acme"

    def test_from_raw_keeps_explicit_company(self):
        job = JobPosting.from_raw(
            {"title": "Backend", "link": "x", "company": "Nubank"})
        assert job.company == "Nubank"

    def test_from_raw_accepts_date_alias(self):
        job = JobPosting.from_raw(
            {"title": "Dev", "link": "x", "published": "2026-05-06"})
        assert job.posted_at == dt.datetime(2026, 5, 6)

    def test_from_raw_fills_source_from_domain(self):
        job = JobPosting.from_raw(
            {"title": "Dev", "link": "x", "domain": "boards.greenhouse.io"})
        assert job.source == "boards.greenhouse.io"
        assert job.domain == "boards.greenhouse.io"

    def test_from_raw_preserves_identity_fields(self):
        job = JobPosting.from_raw(
            {"title": "Dev", "link": "x", "provider": "greenhouse",
             "external_id": "42"})
        assert job.provider == "greenhouse"
        assert job.external_id == "42"
