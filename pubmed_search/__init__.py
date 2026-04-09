"""pubmed-search: Search PubMed and generate BibTeX references."""

from .api import PubMedClient, Article
from .doi import validate_doi, validate_dois, search_doi_by_title

__version__ = "1.0.0"
__all__ = ["PubMedClient", "Article", "validate_doi", "validate_dois", "search_doi_by_title"]
