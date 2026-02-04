from .models import ExtractResult
import trafilatura


# Step C： Extract main text from HTM
def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def _extract_metadata_compat(html: str, url: str):
    """
    兼容不同版本 trafilatura 的 extract_metadata 签名：
    - 有的版本支持 extract_metadata(html, url=...)
    - 有的版本只支持 extract_metadata(html)
    """
    try:
        return trafilatura.extract_metadata(html, url=url)
    except TypeError:
        return trafilatura.extract_metadata(html)


def extract_main_text(html: str, url: str, min_text_length: int) -> ExtractResult:
    text = trafilatura.extract(
        html,
        url=url,  # extract() support url，用于更好的链接解析/抽取
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )

    meta = _extract_metadata_compat(html, url=url)

    title = getattr(meta, "title", None) if meta else None
    author = getattr(meta, "author", None) if meta else None
    date = getattr(meta, "date", None) if meta else None
    language = getattr(meta, "language", None) if meta else None
    description = getattr(meta, "description", None) if meta else None

    norm = _normalize_ws(text) if text else None
    text_ok = bool(norm) and len(norm) >= min_text_length

    return ExtractResult(
        text_ok=text_ok, title=title, author=author, date=date, language=language, description=description, text=norm
    )
