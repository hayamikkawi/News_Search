# requirements: fastapi, httpx, beautifulsoup4, transformers, torch (cpu), trafilatura (optional)

import asyncio
import logging
from common_utils.types import DocID
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Request
from transformers import pipeline

router = APIRouter()

# load once (slow to load, keep global)
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

def extract_text_basic(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())
    return text

async def fetch_url(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url, timeout=8.0, follow_redirects=True, headers={"User-Agent": "ttds-bot/1.0"})
    r.raise_for_status()
    return r.text

def summarize_text(text: str) -> str:
    # keep input bounded
    text = text[:8000]
    out = summarizer(text, max_length=140, min_length=60, do_sample=False)
    return out[0]["summary_text"]

@router.post("/summarize")
async def summarize(request: Request, query: str, ids: list[str], k: int = 5):
    # 1) get top k elements
    first_k_ids = ids[:k]
    logging.info(f"ids: {first_k_ids}")
    # 2) get urls for ids from DB (your code)
    urls = request.app.state.store.fetch_urls_by_ids(first_k_ids)
    logging.info(f"urls: {urls}")
    # 3) fetch pages concurrently
    async with httpx.AsyncClient() as client:
        pages = await asyncio.gather(*(fetch_url(client, u) for u in urls), return_exceptions=True)
    # 4) extract text, skip failures
    texts = []
    used_ids = []
    for doc_id, url, page in zip(ids, urls, pages):
        if isinstance(page, Exception):
            continue
        text = extract_text_basic(page)
        logging.info(f"text: {text}")
        if len(text) > 200:
            texts.append(text)
            used_ids.append(doc_id)

    if not texts:
        raise HTTPException(502, "Could not fetch any article text to summarize")

    # 5) summarize each, then summarize the summaries (two-stage)
    per_article_summaries = await asyncio.to_thread(
        lambda: [summarize_text(t) for t in texts]
    )
    combined = "\n".join(per_article_summaries)
    logging.info(f"combined: {combined}")
    final_summary = await asyncio.to_thread(lambda: summarize_text(combined))
    logging.info(f"final_summary: {final_summary}")
    return {"summary": final_summary, "sources": used_ids}