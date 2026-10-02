"""Static configuration: job board/ATS domains and per-country settings."""

from __future__ import annotations

# Generic job boards (work for general searches)
BOARDS = ["indeed.com", "linkedin.com/jobs", "glassdoor.com"]

# ATS used by companies (the hidden gold)
ATS = [
    "boards.greenhouse.io",
    "jobs.lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "jobs.ashbyhq.com",
    "apply.workable.com",
]

GROUPS = {"boards": BOARDS, "ats": ATS, "all": BOARDS + ATS}

# Per-country config. Feel free to edit: "names" are the terms used in the query
# (joined by OR), "region" goes to the backend, "indeed"/"glassdoor" are the
# local domains and "extra" are job boards that exist only in that country.
COUNTRIES = {
    "br": {"names": ["Brazil", "Brasil"], "region": "br-pt", "gl": "br",
           "indeed": "br.indeed.com", "glassdoor": "glassdoor.com.br",
           "extra": ["gupy.io", "infojobs.com.br", "vagas.com.br",
                     "catho.com.br", "programathor.com.br"]},
    "pt": {"names": ["Portugal"], "region": "pt-pt", "gl": "pt",
           "indeed": "pt.indeed.com", "extra": []},
    "us": {"names": ["United States", "USA"], "region": "us-en", "gl": "us",
           "indeed": "indeed.com", "extra": []},
    "uk": {"names": ["United Kingdom", "UK"], "region": "uk-en", "gl": "uk",
           "indeed": "uk.indeed.com", "glassdoor": "glassdoor.co.uk", "extra": []},
    "ca": {"names": ["Canada"], "region": "ca-en", "gl": "ca",
           "indeed": "ca.indeed.com", "glassdoor": "glassdoor.ca", "extra": []},
    "de": {"names": ["Germany", "Deutschland"], "region": "de-de", "gl": "de",
           "indeed": "de.indeed.com", "glassdoor": "glassdoor.de", "extra": []},
    "es": {"names": ["Spain", "España"], "region": "es-es", "gl": "es",
           "indeed": "es.indeed.com", "glassdoor": "glassdoor.es", "extra": []},
    "mx": {"names": ["Mexico", "México"], "region": "mx-es", "gl": "mx",
           "indeed": "mx.indeed.com", "glassdoor": "glassdoor.com.mx", "extra": []},
    "ar": {"names": ["Argentina"], "region": "ar-es", "gl": "ar",
           "indeed": "ar.indeed.com", "glassdoor": "glassdoor.com.ar", "extra": []},
    "co": {"names": ["Colombia"], "region": "co-es", "gl": "co",
           "indeed": "co.indeed.com", "extra": []},
    "cl": {"names": ["Chile"], "region": "cl-es", "gl": "cl",
           "indeed": "cl.indeed.com", "extra": []},
}
