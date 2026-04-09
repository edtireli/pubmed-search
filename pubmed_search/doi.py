"""
DOI validation via doi.org content negotiation and CrossRef API.
"""

import json
import time
from dataclasses import dataclass
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError


@dataclass
class DOIResult:
    doi: str
    valid: bool
    title: str = ""
    authors: str = ""
    journal: str = ""
    year: str = ""
    error: str = ""

    def summary(self) -> str:
        if self.valid:
            return f"  ✓ {self.doi} → {self.title[:80]}"
        return f"  ✗ {self.doi} → {self.error}"


def validate_doi(
    doi: str,
    expected_title: str = "",
    delay: float = 0.5,
) -> DOIResult:
    """Validate a DOI via CrossRef API and return metadata.

    If expected_title is provided, checks that the DOI resolves to a
    matching title (case-insensitive substring match). If it doesn't
    match, the result is marked with a mismatch warning.
    """
    time.sleep(delay)
    url = f"https://api.crossref.org/works/{doi}"
    req = Request(url, headers={
        "User-Agent": "pubmed-search/1.0 (mailto:research@example.com)",
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        item = data.get("message", {})
        title_parts = item.get("title", [])
        title = title_parts[0] if title_parts else ""
        authors_list = item.get("author", [])
        auth_str = ", ".join(
            f"{a.get('family', '')}, {a.get('given', '')}"
            for a in authors_list[:3]
        )
        if len(authors_list) > 3:
            auth_str += " et al."
        journal_parts = item.get("container-title", [])
        journal = journal_parts[0] if journal_parts else ""
        # Year from published-print or published-online
        year = ""
        for date_key in ["published-print", "published-online", "issued"]:
            dp = item.get(date_key, {}).get("date-parts", [[]])
            if dp and dp[0]:
                year = str(dp[0][0])
                break

        # Title cross-validation
        error = ""
        if expected_title and title:
            if not _titles_match(expected_title, title):
                error = f"TITLE MISMATCH: DOI resolves to '{title[:60]}...'"

        return DOIResult(
            doi=doi, valid=True, title=title,
            authors=auth_str, journal=journal, year=year,
            error=error,
        )
    except HTTPError as e:
        if e.code == 404:
            return DOIResult(doi=doi, valid=False, error="DOI not found (404)")
        return DOIResult(doi=doi, valid=False, error=f"HTTP {e.code}")
    except (URLError, TimeoutError) as e:
        return DOIResult(doi=doi, valid=False, error=str(e))


def _titles_match(a: str, b: str, threshold: float = 0.5) -> bool:
    """Check if two titles are similar enough (word overlap ratio)."""
    import re
    wa = set(re.findall(r'\w{3,}', a.lower()))
    wb = set(re.findall(r'\w{3,}', b.lower()))
    if not wa or not wb:
        return False
    overlap = len(wa & wb)
    return overlap / min(len(wa), len(wb)) >= threshold


def search_doi_by_title(title: str, delay: float = 0.5) -> Optional[str]:
    """Search CrossRef for a DOI matching the given title."""
    time.sleep(delay)
    from urllib.parse import quote
    url = f"https://api.crossref.org/works?query.title={quote(title)}&rows=3"
    req = Request(url, headers={
        "User-Agent": "pubmed-search/1.0 (mailto:research@example.com)",
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        items = data.get("message", {}).get("items", [])
        for item in items:
            cr_title = (item.get("title", [None]) or [None])[0]
            if cr_title and _titles_match(title, cr_title):
                return item.get("DOI", "")
    except (HTTPError, URLError, TimeoutError):
        pass
    return None


def validate_dois(dois: list[str], delay: float = 0.5) -> list[DOIResult]:
    """Validate a list of DOIs, with rate limiting."""
    results = []
    for doi in dois:
        results.append(validate_doi(doi, delay=delay))
    return results
