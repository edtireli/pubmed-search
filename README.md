# pubmed-search

Search PubMed from the command line and generate BibTeX references.

Uses NCBI's official [E-utilities API](https://www.ncbi.nlm.nih.gov/books/NBK25500/) — no web-scraping, no captchas.

## Installation

```bash
pip install -e .
```

## Usage

### Search and display results

```bash
pubmed-search "capillary transit time heterogeneity traumatic brain injury" -n 10
```

### Generate BibTeX

```bash
pubmed-search "mTBI pulse oximetry hypoxia" -n 5 --bibtex refs.bib
```

### Fetch specific PMIDs

```bash
pubmed-search --pmids 25052556,24938401,27708611 --bibtex refs.bib
```

### Batch mode (multiple queries from file)

```bash
# queries.txt — one query per line, # for comments
pubmed-search --batch queries.txt -n 10 --bibtex all_refs.bib
```

### Include abstracts

```bash
pubmed-search "concussion SpO2" -n 5 --abstracts
```

### Validate DOIs via CrossRef

```bash
pubmed-search --pmids 25052556 --validate-dois
```

### JSON output

```bash
pubmed-search "CTH DSC-MRI" -n 5 --json results.json --abstracts
```

### Filter by date

```bash
pubmed-search "mTBI cerebral blood flow" -n 20 --min-date 2020 --max-date 2025
```

## API Key (optional, recommended)

Register for a free key at [NCBI](https://www.ncbi.nlm.nih.gov/account/settings/) to increase rate limits from 3 to 10 requests/second.

```bash
export NCBI_API_KEY="your_key_here"
export NCBI_EMAIL="your@email.com"
```

## Python API

```python
from pubmed_search import PubMedClient, validate_dois

client = PubMedClient()

# Search
articles = client.search_and_fetch("mTBI SpO2 hypoxia", max_results=5)
for a in articles:
    print(a.to_bibtex())

# Fetch by PMID
article = client.fetch_by_pmid("25052556")
print(article.title)

# Validate DOIs
results = validate_dois(["10.1038/jcbfm.2014.131", "10.3389/invalid"])
for r in results:
    print(r.summary())
```

## License

MIT
