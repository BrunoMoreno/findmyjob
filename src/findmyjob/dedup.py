"""URL normalization for deduplication."""

from __future__ import annotations

# Query parameters that identify a campaign/referral rather than a job.
# Matched case-insensitively: exact names or prefixes.
#
# `gh_jid` is intentionally NOT listed: on Greenhouse-hosted boards it is the
# job identifier (e.g. https://acme.com/jobs?gh_jid=123), so stripping it would
# collapse distinct jobs into a single dedup key.
_TRACKING_PREFIXES = ("utm_", "mc_", "lever-")
_TRACKING_EXACT = {
    "gclid", "fbclid", "dclid", "msclkid", "yclid", "gbraid", "wbraid",
    "ref", "referrer", "source", "src", "trk", "tracking", "trkcampaign",
    "gh_src", "_hsenc", "_hsmi", "mkt_tok", "_ga", "_gl", "igshid",
}


def _is_tracking(name: str) -> bool:
    lowered = name.lower()
    return lowered in _TRACKING_EXACT or lowered.startswith(_TRACKING_PREFIXES)


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication: drop tracking, fragment and trailing slash."""
    if not url:
        return url
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not _is_tracking(k)]
    path = parts.path.rstrip("/") or "/"
    netloc = parts.netloc.lower()
    return urlunsplit((parts.scheme.lower(), netloc, path,
                       urlencode(query), ""))
