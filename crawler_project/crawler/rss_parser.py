from typing import List, Optional
import feedparser
from dateutil import parser as dtparser
from .models import RssEntry

#Step A
def _to_iso(dt_str: Optional[str]) -> Optional[str]:
    if not dt_str:
        return None
    try:
        return dtparser.parse(dt_str).isoformat()
    except Exception:
        return None

def parse_feed(feed_url: str, max_items: int) -> List[RssEntry]:
    feed = feedparser.parse(feed_url)
    items: List[RssEntry] = []

    for e in feed.entries[:max_items]:
        url = getattr(e, "link", None)
        if not url:
            continue
        title = getattr(e, "title", None)
        published = getattr(e, "published", None) or getattr(e, "updated", None)
        items.append(RssEntry(
            url=url,
            rss_title=title,
            rss_published_at=_to_iso(published),
            feed_url=feed_url
        ))

    # 去重
    seen = set()
    uniq: List[RssEntry] = []
    for it in items:
        if it.url in seen:
            continue
        seen.add(it.url)
        uniq.append(it)

    return uniq
