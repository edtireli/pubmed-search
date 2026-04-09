#!/usr/bin/env python3
"""
CLI for pubmed-search: search PubMed, fetch metadata, output BibTeX.

Usage:
  pubmed-search "capillary transit time heterogeneity" -n 10 --bibtex refs.bib
  pubmed-search --pmids 25052556,24938401 --bibtex refs.bib
  pubmed-search "mTBI SpO2 hypoxia" -n 5 --validate-dois
  pubmed-search --batch queries.txt --bibtex all_refs.bib
"""

import argparse
import json
import os
import sys
import time

from .api import PubMedClient, Article
from .doi import validate_dois, validate_doi, search_doi_by_title


def main():
    parser = argparse.ArgumentParser(
        prog="pubmed-search",
        description="Search PubMed and generate BibTeX references.",
    )
    parser.add_argument(
        "query", nargs="?", default=None,
        help="PubMed search query (supports full PubMed syntax)",
    )
    parser.add_argument(
        "-n", "--max-results", type=int, default=10,
        help="Maximum results per query (default: 10)",
    )
    parser.add_argument(
        "--sort", choices=["relevance", "pub_date", "Author", "JournalName"],
        default="relevance", help="Sort order (default: relevance)",
    )
    parser.add_argument(
        "--min-date", help="Minimum publication date (YYYY or YYYY/MM/DD)",
    )
    parser.add_argument(
        "--max-date", help="Maximum publication date (YYYY or YYYY/MM/DD)",
    )
    parser.add_argument(
        "--pmids", help="Comma-separated PMIDs to fetch directly",
    )
    parser.add_argument(
        "--batch", help="File with one query per line (batch mode)",
    )
    parser.add_argument(
        "--bibtex", "-b", help="Output BibTeX to file (- for stdout)",
    )
    parser.add_argument(
        "--json", "-j", dest="json_out", help="Output JSON to file (- for stdout)",
    )
    parser.add_argument(
        "--abstracts", "-a", action="store_true",
        help="Include abstracts in output",
    )
    parser.add_argument(
        "--validate-dois", "-v", action="store_true",
        help="Validate DOIs via CrossRef after fetching",
    )
    parser.add_argument(
        "--api-key", default=os.environ.get("NCBI_API_KEY"),
        help="NCBI API key (or set NCBI_API_KEY env var)",
    )
    parser.add_argument(
        "--email", default=os.environ.get("NCBI_EMAIL"),
        help="Email for NCBI (recommended; or set NCBI_EMAIL env var)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.0,
        help="Custom delay between requests in seconds (0 = auto)",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress progress messages",
    )

    args = parser.parse_args()

    if not args.query and not args.pmids and not args.batch:
        parser.print_help()
        sys.exit(1)

    client = PubMedClient(
        api_key=args.api_key,
        email=args.email,
        delay=args.delay,
    )

    all_articles: list[Article] = []
    seen_pmids: set[str] = set()

    def add_articles(articles: list[Article]):
        for a in articles:
            if a.pmid not in seen_pmids:
                seen_pmids.add(a.pmid)
                all_articles.append(a)

    def log(msg: str):
        if not args.quiet:
            print(msg, file=sys.stderr)

    # --- Direct PMID fetch ---
    if args.pmids:
        pmid_list = [p.strip() for p in args.pmids.split(",") if p.strip()]
        log(f"Fetching {len(pmid_list)} PMIDs...")
        add_articles(client.fetch(pmid_list))
        log(f"  → {len(all_articles)} articles fetched")

    # --- Single query ---
    if args.query:
        log(f'Searching: "{args.query}" (max {args.max_results})...')
        articles = client.search_and_fetch(
            args.query, args.max_results, args.sort,
            args.min_date, args.max_date,
        )
        add_articles(articles)
        log(f"  → {len(articles)} results")

    # --- Batch mode ---
    if args.batch:
        with open(args.batch) as f:
            queries = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        log(f"Batch mode: {len(queries)} queries")
        for i, q in enumerate(queries, 1):
            log(f"  [{i}/{len(queries)}] Searching: \"{q}\"...")
            articles = client.search_and_fetch(
                q, args.max_results, args.sort,
                args.min_date, args.max_date,
            )
            add_articles(articles)
            log(f"    → {len(articles)} results ({len(all_articles)} total unique)")
            if i < len(queries):
                time.sleep(1.0)  # Extra pause between batch queries

    log(f"\nTotal: {len(all_articles)} unique articles")

    # --- Display results ---
    if not args.quiet:
        print("\n" + "=" * 70, file=sys.stderr)
        for i, a in enumerate(all_articles, 1):
            print(f"\n{i}. {a.summary()}", file=sys.stderr)
            if args.abstracts and a.abstract:
                # Wrap abstract text
                words = a.abstract.split()
                line = "   "
                for w in words:
                    if len(line) + len(w) + 1 > 80:
                        print(line, file=sys.stderr)
                        line = "   " + w
                    else:
                        line += " " + w
                if line.strip():
                    print(line, file=sys.stderr)
        print("=" * 70, file=sys.stderr)

    # --- Validate DOIs ---
    if args.validate_dois:
        log(f"\nValidating {len(all_articles)} DOIs via CrossRef (with title cross-check)...")
        valid_count = 0
        mismatch_count = 0
        fixed_count = 0
        for a in all_articles:
            if not a.doi:
                log(f"  ○ [{a.pmid}] No DOI — searching CrossRef by title...")
                found = search_doi_by_title(a.title, delay=0.5)
                if found:
                    a.doi = found
                    fixed_count += 1
                    log(f"    → Found: {found}")
                else:
                    log(f"    → Not found")
                continue
            r = validate_doi(a.doi, expected_title=a.title, delay=0.5)
            if r.valid and not r.error:
                valid_count += 1
                log(f"  ✓ [{a.pmid}] {a.doi}")
            elif r.valid and r.error:
                mismatch_count += 1
                log(f"  ⚠ [{a.pmid}] {a.doi} — {r.error}")
                # Try to find correct DOI
                found = search_doi_by_title(a.title, delay=0.5)
                if found and found != a.doi:
                    log(f"    → Auto-fixed to: {found}")
                    a.doi = found
                    fixed_count += 1
                else:
                    log(f"    → Could not auto-fix")
            else:
                log(f"  ✗ [{a.pmid}] {a.doi} — {r.error}")
        log(f"\n  Summary: {valid_count} valid, {mismatch_count} mismatches, {fixed_count} auto-fixed")

    # --- BibTeX output ---
    if args.bibtex:
        # Deduplicate citekeys
        used_keys: dict[str, int] = {}
        bib_lines = []
        for a in all_articles:
            key = a.citekey
            if key in used_keys:
                used_keys[key] += 1
                # Modify the citekey to avoid duplicates
                suffix = chr(ord('a') + used_keys[key] - 1)
                bib = a.to_bibtex().replace(f"@article{{{key},", f"@article{{{key}{suffix},", 1)
            else:
                used_keys[key] = 1
                bib = a.to_bibtex()
            bib_lines.append(bib)

        bib_text = "\n\n".join(bib_lines) + "\n"
        if args.bibtex == "-":
            print(bib_text)
        else:
            with open(args.bibtex, "w") as f:
                f.write(bib_text)
            log(f"\nBibTeX written to {args.bibtex}")

    # --- JSON output ---
    if args.json_out:
        data = []
        for a in all_articles:
            d = {
                "pmid": a.pmid, "title": a.title, "authors": a.authors,
                "journal": a.journal, "year": a.year, "volume": a.volume,
                "issue": a.issue, "pages": a.pages, "doi": a.doi,
                "keywords": a.keywords, "citekey": a.citekey,
            }
            if args.abstracts:
                d["abstract"] = a.abstract
            data.append(d)
        json_text = json.dumps(data, indent=2, ensure_ascii=False)
        if args.json_out == "-":
            print(json_text)
        else:
            with open(args.json_out, "w") as f:
                f.write(json_text)
            log(f"JSON written to {args.json_out}")


if __name__ == "__main__":
    main()
