"""Best-effort company extraction from job links and titles."""

from __future__ import annotations

import re
import unicodedata

# Patterns that expose the company name in ATS/job board URLs.
_COMPANY_URL_PATTERNS = [
    re.compile(r"jobs\.lever\.co/([^/?#]+)", re.I),
    re.compile(r"(?:boards|job-boards)\.greenhouse\.io/([^/?#]+)", re.I),
    re.compile(r"apply\.workable\.com/([^/?#]+)", re.I),
    re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)", re.I),
    re.compile(r"smartrecruiters\.com/([^/?#]+)", re.I),
    re.compile(r"indeed\.[a-z.]+/cmp/([^/?#]+)", re.I),
    re.compile(r"glassdoor\.[a-z.]+/(?:Overview|Jobs)/[^/]*?EI_IE\d+\.\d+,\d+_([^/?#]+)", re.I),
]

_SUBDOMAIN_ATS = [
    re.compile(r"^(?P<company>[^.]+)\.gupy\.io$", re.I),
    re.compile(r"^(?P<company>[^.]+)\.(?:wd\d+\.)?myworkdayjobs\.com$", re.I),
]

# Titles often look like "Role at Company", "Role - Company", "Role | Company".
# The capture group deliberately excludes "-" so that
# "Software Engineer - Python - Stone Pagamentos" resolves to "Stone Pagamentos"
# instead of the whole trailing chunk.
_TITLE_AT_PATTERN = re.compile(r"\s+(?:at|@)\s+([^|,•·]{2,40})$", re.I)
_TITLE_SPLIT = re.compile(r"\s*[|•·]\s*|\s+[-–—]\s+")

# Tokens that look like a trailing title segment but are never a company.
_NON_COMPANY_TOKENS = {
    # work model
    "remote", "remoto", "remota", "hybrid", "híbrido", "hibrido", "on-site",
    "onsite", "home office", "full-time", "full time", "part-time", "part time",
    "contract", "contrato", "temporary", "temporário", "temporario", "internship",
    "estágio", "estagio", "freelance", "permanent", "efetivo", "presencial",
    # seniority
    "junior", "júnior", "jr", "pleno", "senior", "sênior", "sr", "lead", "staff",
    "principal", "intern", "trainee", "especialista", "master",
    # common cities / regions (pt-br / pt-pt)
    "são paulo", "sao paulo", "rio de janeiro", "belo horizonte", "brasília",
    "brasilia", "curitiba", "porto alegre", "recife", "salvador", "fortaleza",
    "florianópolis", "florianopolis", "campinas", "goiânia", "goiania", "manaus",
    "lisboa", "porto", "braga", "coimbra", "funchal", "latam", "europe", "emea",
    # countries
    "brasil", "brazil", "portugal", "españa", "espana", "spain", "mexico",
    "méxico", "argentina", "colombia", "chile", "usa", "united states", "uk",
}

# Single words that are roles/technologies, never companies.
_ROLE_WORDS = {
    "python", "java", "javascript", "typescript", "golang", "go", "rust", "php",
    "ruby", "react", "angular", "vue", "node", "backend", "frontend", "fullstack",
    "full-stack", "developer", "engineer", "eng", "dev", "qa", "devops", "sre",
    "data", "analyst", "designer", "design", "product", "manager", "architect",
    "mobile", "ios", "android", "cloud", "security", "support", "sales",
}


def _ascii_lower(text: str) -> str:
    """Lowercase and strip accents, for tolerant comparisons."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def _pretty_company(token: str) -> str:
    """Convert a slug/domain into a readable name: 'acme-corp' -> 'Acme Corp'."""
    token = token.strip()
    token = re.sub(r"\.(com|io|co|jobs|net|org).*$", "", token, flags=re.I)
    token = re.sub(r"[-_+]+", " ", token)
    token = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", token)
    token = re.sub(r"\s+", " ", token).strip()
    if not token:
        return ""
    if token.islower() or token.isupper():
        return token.title()
    return token


def _looks_like_company(candidate: str) -> bool:
    """Heuristics to reject trailing title segments that are not companies."""
    candidate = candidate.strip().strip(".,;:!?()[]")
    if not (2 <= len(candidate) <= 40) or not candidate[0].isalpha():
        return False
    lowered = _ascii_lower(candidate)
    if lowered in _NON_COMPANY_TOKENS:
        return False
    # "São Paulo, SP" / "Remote - Brazil" style tails.
    head = _ascii_lower(re.split(r"[,(]", candidate)[0])
    if head in _NON_COMPANY_TOKENS:
        return False
    if " " not in candidate and lowered in _ROLE_WORDS:
        return False
    # A trailing location/seniority token ("Acme - Remote").
    if _ascii_lower(candidate.split()[-1]) in _NON_COMPANY_TOKENS:
        return False
    return True


def _company_from_title(title: str) -> str:
    clean = title.strip()
    if not clean:
        return ""
    at_match = _TITLE_AT_PATTERN.search(clean)
    if at_match:
        candidate = at_match.group(1).strip()
        if _looks_like_company(candidate):
            return candidate
    parts = [p.strip() for p in _TITLE_SPLIT.split(clean) if p.strip()]
    if len(parts) >= 2:
        candidate = parts[-1]
        if _looks_like_company(candidate):
            return candidate
    return ""


def extract_company(link: str = "", title: str = "") -> str:
    """
    Extract the company name from the link (ATS/job boards) or the title.

    Link-based extraction is reliable for ATS URLs. Title-based extraction is a
    best effort and returns an empty string when it cannot identify a company.
    """
    from urllib.parse import urlsplit

    if link:
        try:
            host = urlsplit(link).netloc.lower().split(":")[0]
        except ValueError:
            host = ""
        for pattern in _SUBDOMAIN_ATS:
            m = pattern.match(host)
            if m:
                return _pretty_company(m.group("company"))
        for pattern in _COMPANY_URL_PATTERNS:
            m = pattern.search(link)
            if m:
                return _pretty_company(m.group(1))

    if title:
        candidate = _company_from_title(title)
        if candidate:
            return _pretty_company(candidate)
    return ""
