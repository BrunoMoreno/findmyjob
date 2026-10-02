"""Canonical job-posting model shared by every source.

The pipeline historically passed plain dictionaries around. ``JobPosting`` is
the stable, documented contract: it validates and normalises raw results coming
from the search backends and the ATS JSON APIs, and serialises back to the dict
shape used by the file outputs and the SQLite sink.

The SQLite ``jobs`` table mirrors these fields (see ``findmyjob.db``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from .dates import parse_posted_date
from .dedup import normalize_url
from .enrich import extract_company

# Text fields that must never be ``None``; they are coerced to "" instead.
_TEXT_FIELDS = (
    "title", "link", "company", "location", "description", "snippet",
    "domain", "source", "query", "provider", "external_id",
)

# Alternative keys that carry the posting date in raw results.
_DATE_ALIASES = ("date", "published", "first_published")


class JobPosting(BaseModel):
    """
    Canonical, source-agnostic job posting.

    Fields:

    - ``provider``: ATS provider (``greenhouse``, ``lever``, ...) when known.
    - ``external_id``: the posting id assigned by the source. Empty for dork
      results, which do not expose one.
    - ``posted_at``: parsed to a ``datetime`` on construction and serialised as
      ISO 8601 by :meth:`to_dict`.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str = ""
    link: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    snippet: str = ""
    domain: str = ""
    source: str = ""
    query: str = ""
    provider: str = ""
    external_id: str = ""
    posted_at: datetime | None = None

    @field_validator(*_TEXT_FIELDS, mode="before")
    @classmethod
    def _coerce_text(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator("posted_at", mode="before")
    @classmethod
    def _coerce_posted_at(cls, value: Any) -> Any:
        if value is not None and not isinstance(value, datetime):
            if isinstance(value, str) and value.strip():
                # ISO 8601 first (keeps the timezone offset); then relative text.
                try:
                    value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
                except ValueError:
                    value = parse_posted_date(value)
            else:
                value = parse_posted_date(value)
        if isinstance(value, datetime):
            return value.replace(microsecond=0)
        return None

    @property
    def link_key(self) -> str:
        """Normalised URL used as the deduplication key."""
        return normalize_url(self.link)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-serialisable dict (``posted_at`` as ISO 8601)."""
        return self.model_dump(mode="json")

    @classmethod
    def from_raw(cls, job: Mapping[str, Any]) -> JobPosting:
        """
        Build a posting from a raw result dict.

        A missing ``company`` is derived from the link/title (best effort) and
        the date aliases ``date``/``published``/``first_published`` are accepted.
        """
        data = dict(job)
        if not data.get("company"):
            data["company"] = extract_company(data.get("link", ""), data.get("title", ""))
        if not data.get("posted_at"):
            for alias in _DATE_ALIASES:
                if data.get(alias):
                    data["posted_at"] = data[alias]
                    break
        if not data.get("source") and data.get("domain"):
            data["source"] = data["domain"]
        if not data.get("domain") and data.get("source"):
            data["domain"] = data["source"]
        return cls(**data)
