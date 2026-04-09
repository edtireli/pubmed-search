"""
PubMed E-utilities API client with rate limiting.

Uses NCBI's official REST API:
  https://www.ncbi.nlm.nih.gov/books/NBK25500/

Rate limits:
  - Without API key: 3 requests/second
  - With API key: 10 requests/second
  Register for a key at: https://www.ncbi.nlm.nih.gov/account/settings/
"""

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@dataclass
class Article:
    pmid: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    journal_abbrev: str = ""
    year: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    pmc: str = ""

    @property
    def first_author_last(self) -> str:
        if self.authors:
            parts = self.authors[0].split()
            return parts[-1] if parts else "Unknown"
        return "Unknown"

    @property
    def citekey(self) -> str:
        return f"{self.first_author_last}{self.year}"

    def to_bibtex(self) -> str:
        lines = [f"@article{{{self.citekey},"]
        lines.append(f"  author  = {{{' and '.join(self.authors)}}},")
        lines.append(f"  title   = {{{self.title}}},")
        lines.append(f"  journal = {{{self.journal}}},")
        lines.append(f"  year    = {{{self.year}}},")
        if self.volume:
            lines.append(f"  volume  = {{{self.volume}}},")
        if self.issue:
            lines.append(f"  number  = {{{self.issue}}},")
        if self.pages:
            lines.append(f"  pages   = {{{self.pages}}},")
        if self.doi:
            lines.append(f"  doi     = {{{self.doi}}},")
        if self.pmid:
            lines.append(f"  pmid    = {{{self.pmid}}},")
        lines.append("}")
        return "\n".join(lines)

    def summary(self) -> str:
        auths = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            auths += " et al."
        return (
            f"[{self.pmid}] {auths} ({self.year}). {self.title} "
            f"{self.journal_abbrev or self.journal}. "
            f"doi:{self.doi}" if self.doi else
            f"[{self.pmid}] {auths} ({self.year}). {self.title} "
            f"{self.journal_abbrev or self.journal}."
        )

    def __repr__(self) -> str:
        return f"Article(pmid={self.pmid!r}, title={self.title[:60]!r}...)"


class PubMedClient:
    """Rate-limited PubMed E-utilities client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        email: Optional[str] = None,
        tool: str = "pubmed-search",
        delay: float = 0.0,
    ):
        self.api_key = api_key
        self.email = email
        self.tool = tool
        # Default delay: 0.35s without key (< 3/s), 0.12s with key (< 10/s)
        self.delay = delay if delay > 0 else (0.12 if api_key else 0.35)
        self._last_request = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()

    def _build_params(self, **kwargs) -> dict:
        params = {"tool": self.tool}
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        params.update({k: v for k, v in kwargs.items() if v is not None})
        return params

    def _get(self, endpoint: str, **kwargs) -> bytes:
        self._rate_limit()
        params = self._build_params(**kwargs)
        url = f"{BASE_URL}/{endpoint}?{urlencode(params)}"
        req = Request(url, headers={"User-Agent": f"{self.tool}/1.0"})
        try:
            with urlopen(req, timeout=30) as resp:
                return resp.read()
        except HTTPError as e:
            if e.code == 429:
                # Too many requests — back off and retry once
                time.sleep(2.0)
                self._last_request = time.time()
                with urlopen(req, timeout=30) as resp:
                    return resp.read()
            raise

    def search(
        self,
        query: str,
        max_results: int = 20,
        sort: str = "relevance",
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
    ) -> list[str]:
        """Search PubMed, return list of PMIDs."""
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": str(max_results),
            "sort": sort,
            "retmode": "xml",
        }
        if min_date:
            params["mindate"] = min_date
            params["datetype"] = "pdat"
        if max_date:
            params["maxdate"] = max_date
            if "datetype" not in params:
                params["datetype"] = "pdat"

        data = self._get("esearch.fcgi", **params)
        root = ET.fromstring(data)
        count_el = root.find(".//Count")
        total = int(count_el.text) if count_el is not None else 0
        pmids = [id_el.text for id_el in root.findall(".//IdList/Id")]
        return pmids

    def fetch(self, pmids: list[str], batch_size: int = 50) -> list[Article]:
        """Fetch full article metadata for a list of PMIDs."""
        articles = []
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            data = self._get(
                "efetch.fcgi",
                db="pubmed",
                id=",".join(batch),
                retmode="xml",
            )
            root = ET.fromstring(data)
            for art_el in root.findall(".//PubmedArticle"):
                articles.append(self._parse_article(art_el))
        return articles

    def search_and_fetch(
        self,
        query: str,
        max_results: int = 20,
        sort: str = "relevance",
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
    ) -> list[Article]:
        """Search PubMed and fetch full metadata in one call."""
        pmids = self.search(query, max_results, sort, min_date, max_date)
        if not pmids:
            return []
        return self.fetch(pmids)

    def fetch_by_pmid(self, pmid: str) -> Optional[Article]:
        """Fetch a single article by PMID."""
        results = self.fetch([pmid])
        return results[0] if results else None

    @staticmethod
    def _parse_article(art_el: ET.Element) -> Article:
        a = Article()

        # PMID
        pmid_el = art_el.find(".//PMID")
        if pmid_el is not None:
            a.pmid = pmid_el.text or ""

        medline = art_el.find(".//MedlineCitation/Article")
        if medline is None:
            return a

        # Title
        title_el = medline.find("ArticleTitle")
        if title_el is not None:
            a.title = "".join(title_el.itertext()).strip()

        # Abstract
        abs_parts = []
        for abs_el in medline.findall(".//Abstract/AbstractText"):
            label = abs_el.get("Label", "")
            text = "".join(abs_el.itertext()).strip()
            if label:
                abs_parts.append(f"{label}: {text}")
            else:
                abs_parts.append(text)
        a.abstract = " ".join(abs_parts)

        # Authors
        for author_el in medline.findall(".//AuthorList/Author"):
            last = author_el.findtext("LastName", "")
            fore = author_el.findtext("ForeName", "")
            initials = author_el.findtext("Initials", "")
            if last:
                name = f"{last}, {fore}" if fore else f"{last}, {initials}"
                a.authors.append(name)

        # Journal
        journal_el = medline.find("Journal")
        if journal_el is not None:
            a.journal = journal_el.findtext("Title", "")
            a.journal_abbrev = journal_el.findtext("ISOAbbreviation", "")
            ji = journal_el.find("JournalIssue")
            if ji is not None:
                a.volume = ji.findtext("Volume", "")
                a.issue = ji.findtext("Issue", "")
                # Year
                pd = ji.find("PubDate")
                if pd is not None:
                    a.year = pd.findtext("Year", "")
                    if not a.year:
                        medline_date = pd.findtext("MedlineDate", "")
                        if medline_date:
                            a.year = medline_date[:4]

        # Pages
        a.pages = medline.findtext("Pagination/MedlinePgn", "")

        # DOI
        for id_el in art_el.findall(".//ArticleIdList/ArticleId"):
            if id_el.get("IdType") == "doi":
                a.doi = id_el.text or ""
            elif id_el.get("IdType") == "pmc":
                a.pmc = id_el.text or ""

        # Keywords
        for kw_el in art_el.findall(".//KeywordList/Keyword"):
            kw = "".join(kw_el.itertext()).strip()
            if kw:
                a.keywords.append(kw)

        return a
