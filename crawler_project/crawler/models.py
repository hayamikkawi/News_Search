from dataclasses import dataclass
from typing import Optional, Dict, Any
#统一数据结构
@dataclass
class RssEntry:
    url: str
    rss_title: Optional[str]
    rss_published_at: Optional[str]  # ISO8601
    feed_url: str

@dataclass
class FetchResult:
    ok: bool
    status: Optional[int]
    final_url: str
    html: Optional[str]
    error: Optional[str]

@dataclass
class ExtractResult:
    text_ok: bool
    title: Optional[str]
    author: Optional[str]
    date: Optional[str]
    language: Optional[str]
    text: Optional[str]

@dataclass
class ArticleRecord:
    url: str
    final_url: str
    feed_url: str
    rss_title: Optional[str]
    rss_published_at: Optional[str]
    fetched_at: str
    http_status: Optional[int]
    error: Optional[str]
    extracted: Optional[Dict[str, Any]]
