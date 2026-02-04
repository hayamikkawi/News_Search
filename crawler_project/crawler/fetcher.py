from typing import Dict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .models import FetchResult

# Step B:Download article HTML


def build_session() -> requests.Session:
    s = requests.Session()  # Defines when and how failed HTTP requests should be retried
    retry = Retry(
        total=3,  # Maximum number of retry attempts
        backoff_factor=0.8,  # Controls how long the client waits between retry attempts.
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes that trigger retries
        allowed_methods=[
            "GET",
            "HEAD",
        ],  # Only idempotent and safe methods are retried: GET: fetch content，HEAD: metadata-only request
        raise_on_status=False,  # Do not raise exceptions on HTTP error status codes
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def fetch_html(session: requests.Session, url: str, user_agent: str, timeout_seconds: int) -> FetchResult:
    headers: Dict[str, str] = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        r = session.get(url, headers=headers, timeout=timeout_seconds)
        ok = r.status_code < 400 and bool(r.text)
        return FetchResult(ok=ok, status=r.status_code, final_url=r.url, html=r.text if ok else None, error=None)
    except Exception as e:
        return FetchResult(ok=False, status=None, final_url=url, html=None, error=repr(e))
