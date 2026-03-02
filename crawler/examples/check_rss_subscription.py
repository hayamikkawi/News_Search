#!/usr/bin/env python3
"""
Check whether an RSS source likely requires subscription/paywall.

This script:
1. Reads N items from an RSS feed using crawler logic.
2. Fetches and extracts article content.
3. Prints crawled content.
4. Evaluates whether the source likely needs subscription.
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

try:
    from src.config import CONFIG
    from src.core.rss_parser import parse_feed
    from src.core.fetcher import build_session, fetch_html
    from src.core.extractor import extract_main_text
except ImportError:
    from config import CONFIG
    from core.rss_parser import parse_feed
    from core.fetcher import build_session, fetch_html
    from core.extractor import extract_main_text


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


PAYWALL_MARKERS = [
    "subscribe to continue",
    "sign in to continue",
    "login to continue",
    "register to continue",
    "already a subscriber",
    "already subscribed",
    "start your subscription",
    "continue reading with subscription",
    "this content is for subscribers",
    "subscriber-only content",
    "member-only",
    "members only",
    "premium content",
    "this article is behind a paywall",
]


@dataclass
class ArticleCheckResult:
    index: int
    url: str
    final_url: str
    status: int | None
    fetch_ok: bool
    text_ok: bool
    text: str
    text_len: int
    paywall_keywords: List[str]
    blocked_http: bool
    suspected_subscription: bool
    fetch_error: str | None


def _find_paywall_keywords(html: str | None) -> List[str]:
    if not html:
        return []
    lower_html = html.lower()
    found = [k for k in PAYWALL_MARKERS if k in lower_html]
    return sorted(set(found))


def check_rss_source(
    rss_url: str,
    num_items: int,
    timeout_seconds: int,
    min_text_length: int,
) -> List[ArticleCheckResult]:
    entries = parse_feed(rss_url, max_items=num_items)
    session = build_session()

    results: List[ArticleCheckResult] = []

    for idx, entry in enumerate(entries, start=1):
        fetch = fetch_html(
            session=session,
            url=entry.url,
            user_agent=CONFIG.user_agent,
            timeout_seconds=timeout_seconds,
        )

        html = fetch.html if fetch.ok else None
        extracted = extract_main_text(html, fetch.final_url, min_text_length=min_text_length) if html else None

        text = extracted.text if extracted and extracted.text else ""
        text_ok = bool(extracted and extracted.text_ok)
        text_len = len(text)

        keyword_hits = _find_paywall_keywords(html)
        blocked_http = fetch.status in {401, 402, 403, 451}

        # Heuristic:
        # - Explicit blocked status, or
        # - paywall markers + short/failed extraction
        short_or_failed = (not text_ok) or text_len < min_text_length
        suspected = blocked_http or (bool(keyword_hits) and short_or_failed)

        results.append(
            ArticleCheckResult(
                index=idx,
                url=entry.url,
                final_url=fetch.final_url,
                status=fetch.status,
                fetch_ok=fetch.ok,
                text_ok=text_ok,
                text=text,
                text_len=text_len,
                paywall_keywords=keyword_hits,
                blocked_http=blocked_http,
                suspected_subscription=suspected,
                fetch_error=fetch.error,
            )
        )

    return results


def print_results(results: List[ArticleCheckResult], print_full_content: bool, preview_chars: int) -> None:
    for r in results:
        print("\n" + "=" * 100)
        print(f"[{r.index}] URL: {r.url}")
        print(f"    Final URL: {r.final_url}")
        print(
            f"    HTTP: {r.status} | fetch_ok={r.fetch_ok} | text_ok={r.text_ok} "
            f"| text_len={r.text_len} | suspected_subscription={r.suspected_subscription}"
        )
        if r.fetch_error:
            print(f"    Fetch error: {r.fetch_error}")
        if r.suspected_subscription and r.paywall_keywords:
            print(f"    Paywall markers: {', '.join(r.paywall_keywords)}")

        if r.text:
            if print_full_content:
                print("    Content:")
                print(r.text)
            else:
                preview = r.text[:preview_chars]
                print(f"    Content preview ({len(preview)} chars):")
                print(preview)
        else:
            print("    Content: <empty>")


def print_summary(results: List[ArticleCheckResult], min_text_length: int) -> None:
    total = len(results)
    fetched_ok = sum(1 for r in results if r.fetch_ok)
    text_ok = sum(1 for r in results if r.text_ok)
    blocked = sum(1 for r in results if r.blocked_http)
    keyword_hit = sum(1 for r in results if r.paywall_keywords)
    suspected = sum(1 for r in results if r.suspected_subscription)
    short_or_fail = sum(1 for r in results if (not r.text_ok) or (r.text_len < min_text_length))

    ratio = (suspected / total) if total else 0.0

    if ratio >= 0.4:
        verdict = "LIKELY_REQUIRES_SUBSCRIPTION"
    elif ratio >= 0.15:
        verdict = "PARTIALLY_PAYWALLED_OR_UNSTABLE"
    else:
        verdict = "LIKELY_ACCESSIBLE"

    print("\n" + "#" * 100)
    print("SUMMARY")
    print("#" * 100)
    print(f"Total checked: {total}")
    print(f"Fetch OK: {fetched_ok}/{total}")
    print(f"Text extraction OK: {text_ok}/{total}")
    print(f"Blocked HTTP (401/402/403/451): {blocked}/{total}")
    print(f"Paywall marker hits: {keyword_hit}/{total}")
    print(f"Short/failed extraction (<{min_text_length}): {short_or_fail}/{total}")
    print(f"Suspected subscription: {suspected}/{total} ({ratio:.1%})")
    print(f"Verdict: {verdict}")
    print("#" * 100)

    suspected_urls = []
    seen = set()
    for r in results:
        if r.suspected_subscription and r.url not in seen:
            seen.add(r.url)
            suspected_urls.append(r.url)

    print("Suspected subscription URLs:")
    if not suspected_urls:
        print("  - None")
    else:
        for url in suspected_urls:
            print(f"  - {url}")
    print("#" * 100)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check RSS source quality and whether it likely requires subscription"
    )
    parser.add_argument("--rss-url", "-u", required=True, help="RSS URL to test")
    parser.add_argument("--num-items", "-n", type=int, default=20, help="How many RSS entries to check")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=CONFIG.timeout_seconds,
        help=f"HTTP timeout in seconds (default: {CONFIG.timeout_seconds})",
    )
    parser.add_argument(
        "--min-text-length",
        type=int,
        default=CONFIG.min_text_length,
        help=f"Minimum extracted text length threshold (default: {CONFIG.min_text_length})",
    )
    parser.add_argument(
        "--print-full-content",
        action="store_true",
        help="Print full extracted content instead of preview",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=500,
        help="Preview characters when not printing full content (default: 500)",
    )

    args = parser.parse_args()

    logger.info(
        "Checking RSS source: %s (num_items=%d, timeout=%ds, min_text_length=%d)",
        args.rss_url,
        args.num_items,
        args.timeout_seconds,
        args.min_text_length,
    )

    results = check_rss_source(
        rss_url=args.rss_url,
        num_items=args.num_items,
        timeout_seconds=args.timeout_seconds,
        min_text_length=args.min_text_length,
    )

    if not results:
        logger.error("No RSS entries parsed from feed: %s", args.rss_url)
        sys.exit(1)

    print_results(results, print_full_content=args.print_full_content, preview_chars=args.preview_chars)
    print_summary(results, min_text_length=args.min_text_length)


if __name__ == "__main__":
    main()
