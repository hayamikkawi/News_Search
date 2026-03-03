# requirements: fastapi, httpx, beautifulsoup4, transformers, torch (cpu), trafilatura (optional)

import asyncio
import logging
from common_utils.types import DocID
import httpx
from fastapi import APIRouter, HTTPException, Request
import trafilatura
from transformers import pipeline
from pydantic import BaseModel
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer

extractor = TextRankSummarizer()

def extractive_summary(text: str, sentences: int = 5) -> str:
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    sents = extractor(parser.document, sentences)
    return " ".join(str(s) for s in sents)

router = APIRouter()

class SummarizeRequest(BaseModel):
    ids: list[DocID]
    k: int = 3
# load once (slow to load, keep global)
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
tokenizer = summarizer.tokenizer

def get_clean_text(url: str, html: str) -> str:
    txt = trafilatura.extract(html, include_comments=False, include_tables=False)
    return txt or ""

async def fetch_url(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url, timeout=8.0, follow_redirects=True, headers={"User-Agent": "ttds-bot/1.0"})
    r.raise_for_status()
    return r.text

def summarize_text(text: str) -> str:
    # keep input bounded
    text = text[:8000]
    out = summarizer(text, max_length=200, min_length=60, do_sample=False)
    return out[0]["summary_text"]

@router.post("/summarize")
async def summarize(request: Request, body: SummarizeRequest):
    ids = body.ids
    k = body.k
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
        text = get_clean_text(url, page)
        logging.info(f"text: {text}")
        if len(text) > 200:
            texts.append(text)
            used_ids.append(doc_id)

    if not texts:
        raise HTTPException(502, "Could not fetch any article text to summarize")

    # 5) extractive summary for each article (extract top 5 sentences)
    per_article_extracted: list[str] = []
    for text in texts:
        summary = extractive_summary(text, sentences=5)
        logging.info(f"summary: {summary}")
        per_article_extracted.append(summary)
    per_article_summary: list[str] = []
    # 6) summarize each article based on its top 5 snetences.
    for extracted in per_article_extracted:
        summary = await asyncio.to_thread(lambda: summarize_text(extracted))
        per_article_summary.append(summary)
    return {"summary": f"\n".join(per_article_summary), "sources": used_ids} 