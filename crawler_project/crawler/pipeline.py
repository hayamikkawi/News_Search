from typing import List
from .models import ArticleRecord
from .rss_parser import parse_feed
from .fetcher import build_session, fetch_html
from .extractor import extract_main_text
from .utils import utc_now_iso, polite_sleep

#把 A/B/C 串起来
def run_feed_pipeline(
    feed_url: str,
    user_agent: str,
    timeout_seconds: int,
    max_items: int,
    sleep_seconds: float,
    jitter_seconds: float,
    min_text_length: int
) -> List[ArticleRecord]:

    items = parse_feed(feed_url, max_items=max_items)
    session = build_session()

    results: List[ArticleRecord] = []
    for it in items:
        polite_sleep(sleep_seconds, jitter_seconds)

        fetch = fetch_html(
            session=session,
            url=it.url,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds
        )

        fetched_at = utc_now_iso()

        if not fetch.ok or not fetch.html:
            results.append(ArticleRecord(
                url=it.url,
                final_url=fetch.final_url,
                feed_url=it.feed_url,
                rss_title=it.rss_title,
                rss_published_at=it.rss_published_at,
                fetched_at=fetched_at,
                http_status=fetch.status,
                error=fetch.error or f"http_status={fetch.status}",
                extracted=None
            ))
            continue

        extracted = extract_main_text(fetch.html, fetch.final_url, min_text_length=min_text_length)

        results.append(ArticleRecord(
            url=it.url,
            final_url=fetch.final_url,
            feed_url=it.feed_url,
            rss_title=it.rss_title,
            rss_published_at=it.rss_published_at,
            fetched_at=fetched_at,
            http_status=fetch.status,
            error=None if extracted.text_ok else "extract_too_short_or_empty",
            extracted={
                "text_ok": extracted.text_ok,
                "title": extracted.title or it.rss_title,
                "author": extracted.author,
                "date": extracted.date or it.rss_published_at,
                "language": extracted.language,
                "text": extracted.text,
            }
        ))

    return results
