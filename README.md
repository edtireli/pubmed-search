<p align="center">
  <h1 align="center">pubmed-search</h1>
  <p align="center">
    Search PubMed from the command line. Generate BibTeX. Validate DOIs.
  </p>
</p>

<p align="center">
  <a href="https://pypi.org/project/pubmed-search/"><img src="https://img.shields.io/pypi/v/pubmed-search?color=blue" alt="PyPI"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/pypi/pyversions/pubmed-search" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/edtireli/pubmed-search" alt="MIT License"></a>
</p>

---

A zero-dependency Python CLI and library for searching [PubMed](https://pubmed.ncbi.nlm.nih.gov/) via NCBI's official [E-utilities API](https://www.ncbi.nlm.nih.gov/books/NBK25500/). No web scraping, no browser automation, no CAPTCHAs.

## Features

- **Search** PubMed with full query syntax (Boolean operators, MeSH terms, field tags)
- **Fetch** article metadata by PMID
- **BibTeX** output — ready to drop into your LaTeX project
- **JSON** output with full metadata and abstracts
- **Batch mode** — run multiple queries from a file with automatic rate limiting
- **DOI validation** via CrossRef with title cross-checking and auto-correction
- **Date filtering** — restrict results to a publication date range
- **Rate limiting** — built-in, respects NCBI guidelines (3 req/s without key, 10 req/s with key)
- **Zero dependencies** — pure Python 3.10+, uses only the standard library

## Installation

### From source

```bash
git clone https://github.com/edtireli/pubmed-search.git
cd pubmed-search
pip install -e .
```

### From PyPI (coming soon)

```bash
pip install pubmed-search
```

## Quick Start

```bash
# Search and display results
pubmed-search "capillary transit time heterogeneity traumatic brain injury" -n 10

# Generate BibTeX
pubmed-search "mTBI pulse oximetry hypoxia" -n 5 --bibtex refs.bib

# Fetch specific articles by PMID
pubmed-search --pmids 25052556,24938401,27708611 --bibtex refs.bib

# Validate that DOIs actually resolve to the correct paper
pubmed-search --pmids 25052556,36369740 --validate-dois --bibtex refs.bib
```

## Usage

### Search PubMed

```bash
# Basic search
pubmed-search "concussion cerebral blood flow" -n 20

# With date range
pubmed-search "mTBI cerebral blood flow" -n 20 --min-date 2020 --max-date 2025

# Sort by date instead of relevance
pubmed-search "CTH DSC-MRI" -n 10 --sort pub_date

# Include abstracts in output
pubmed-search "concussion SpO2" -n 5 --abstracts
```

### Fetch by PMID

```bash
# Fetch specific papers
pubmed-search --pmids 25052556,24938401,27708611

# With BibTeX output
pubmed-search --pmids 25052556 --bibtex refs.bib
```

### Batch Mode

Run multiple queries from a file — one query per line, `#` for comments:

```bash
# queries.txt
# Capillary dysfunction in TBI
"capillary transit time heterogeneity" AND "traumatic brain injury"
"normobaric hypoxia" AND "mild traumatic brain injury"
"pulse oximetry" AND "concussion"
```

```bash
pubmed-search --batch queries.txt -n 10 --bibtex all_refs.bib --json results.json
```

Results are automatically deduplicated across queries.

### DOI Validation

PubMed's XML metadata sometimes contains incorrect DOIs. The `--validate-dois` flag checks each DOI against CrossRef and **auto-fixes mismatches** by searching for the correct DOI by title:

```bash
pubmed-search --pmids 25052556,36369740,27708611 --validate-dois --bibtex refs.bib
```

Output:
```
Validating 3 DOIs via CrossRef (with title cross-check)...
  ✓ [36369740] 10.1177/0271678X221139084
  ⚠ [25052556] 10.1038/jcbfm.2014.118 — TITLE MISMATCH
    → Auto-fixed to: 10.1038/jcbfm.2014.131
  ✓ [27708611] 10.3389/fneur.2016.00149
```

### Output Formats

```bash
# BibTeX file
pubmed-search "mTBI SpO2" -n 5 --bibtex refs.bib

# BibTeX to stdout
pubmed-search "mTBI SpO2" -n 5 --bibtex -

# JSON file (includes abstracts)
pubmed-search "mTBI SpO2" -n 5 --json results.json --abstracts

# Both at once
pubmed-search "mTBI SpO2" -n 5 --bibtex refs.bib --json results.json
```

## Python API

```python
from pubmed_search import PubMedClient, validate_doi, validate_dois, search_doi_by_title

client = PubMedClient()

# Search and fetch
articles = client.search_and_fetch("mTBI SpO2 hypoxia", max_results=5)
for article in articles:
    print(article.summary())
    print(article.to_bibtex())

# Fetch a single article by PMID
article = client.fetch_by_pmid("25052556")
print(article.title)
print(article.doi)

# Validate a DOI (checks it resolves AND matches the expected title)
result = validate_doi("10.1038/jcbfm.2014.131", expected_title="Capillary transit time heterogeneity")
print(result.valid)   # True
print(result.title)   # Full title from CrossRef

# Search CrossRef for a DOI by title
doi = search_doi_by_title("Capillary transit time heterogeneity and flow-metabolism coupling after traumatic brain injury")
print(doi)  # "10.1038/jcbfm.2014.131"

# Batch validate
results = validate_dois(["10.1038/jcbfm.2014.131", "10.3389/fneur.2016.00149"])
for r in results:
    print(r.summary())
```

### Article Object

```python
article = client.fetch_by_pmid("25052556")

article.pmid          # "25052556"
article.title         # "Capillary transit time heterogeneity..."
article.authors       # ["Østergaard, Leif", "Engedal, Thorbjørn S.", ...]
article.journal       # "Journal of Cerebral Blood Flow and Metabolism"
article.journal_abbrev  # "J Cereb Blood Flow Metab"
article.year          # "2014"
article.volume        # "34"
article.issue         # "10"
article.pages         # "1585-1598"
article.doi           # "10.1038/jcbfm.2014.131"
article.abstract      # Full abstract text
article.keywords      # ["brain injuries", "capillaries", ...]
article.pmc           # PMC ID if available
article.citekey       # "Østergaard2014" (auto-generated)
article.to_bibtex()   # Full BibTeX entry
article.summary()     # One-line summary
```

## NCBI API Key (Recommended)

Without an API key, NCBI allows 3 requests/second. With a free key, you get 10 requests/second. Register at [NCBI Settings](https://www.ncbi.nlm.nih.gov/account/settings/).

```bash
# Set via environment variables
export NCBI_API_KEY="your_key_here"
export NCBI_EMAIL="your@email.com"

# Or pass directly
pubmed-search "query" --api-key YOUR_KEY --email your@email.com
```

## All CLI Options

```
usage: pubmed-search [-h] [-n MAX_RESULTS] [--sort {relevance,pub_date,Author,JournalName}]
                     [--min-date MIN_DATE] [--max-date MAX_DATE] [--pmids PMIDS]
                     [--batch BATCH] [--bibtex BIBTEX] [--json JSON] [--abstracts]
                     [--validate-dois] [--api-key API_KEY] [--email EMAIL]
                     [--delay DELAY] [--quiet]
                     [query]

positional arguments:
  query                 PubMed search query (supports full PubMed syntax)

options:
  -n, --max-results     Maximum results per query (default: 10)
  --sort                Sort order: relevance, pub_date, Author, JournalName
  --min-date            Minimum publication date (YYYY or YYYY/MM/DD)
  --max-date            Maximum publication date (YYYY or YYYY/MM/DD)
  --pmids               Comma-separated PMIDs to fetch directly
  --batch               File with one query per line (batch mode)
  -b, --bibtex          Output BibTeX to file (use - for stdout)
  -j, --json            Output JSON to file (use - for stdout)
  -a, --abstracts       Include abstracts in output
  -v, --validate-dois   Validate DOIs via CrossRef with title cross-check
  --api-key             NCBI API key (or set NCBI_API_KEY env var)
  --email               Email for NCBI (or set NCBI_EMAIL env var)
  --delay               Custom delay between requests in seconds
  -q, --quiet           Suppress progress messages
```

## Why This Exists

PubMed is the primary literature database for biomedical research, but getting references out of it and into your LaTeX manuscript is surprisingly annoying. Existing tools either scrape the web (and get blocked), require heavyweight dependencies, or don't output BibTeX.

This tool uses NCBI's official E-utilities API, requires zero dependencies beyond Python 3.10, and handles the things that trip you up in practice — like PubMed returning [incorrect DOIs](https://github.com/edtireli/pubmed-search#doi-validation) that silently break your bibliography.

## Contributing

Pull requests welcome. The codebase is intentionally small (~400 lines across 3 modules):

| Module | Purpose |
|--------|---------|
| `pubmed_search/api.py` | E-utilities client, Article dataclass, BibTeX generation |
| `pubmed_search/doi.py` | CrossRef DOI validation and title-based lookup |
| `pubmed_search/cli.py` | Command-line interface |

## License

[MIT](LICENSE)
