# requirements: fastapi, httpx, beautifulsoup4, transformers, torch (cpu), trafilatura (optional)

import asyncio
import logging
from common_utils.types import DocID
import httpx
from bs4 import BeautifulSoup
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

# def extract_text_basic(html: str) -> str:
#     soup = BeautifulSoup(html, "html.parser")
#     for tag in soup(["script", "style", "nav", "footer", "header"]):
#         tag.decompose()
#     text = " ".join(soup.get_text(" ").split())
#     return text

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

    # 5) summarize each, then summarize the summaries (two-stage)
    # per_article_summaries = await asyncio.to_thread(
    #     lambda: [summarize_long_text(t) for t in texts]
    # )
    # combined = "\n".join(per_article_summaries)
    # logging.info(f"combined: {combined}")
    # final_summary = await asyncio.to_thread(lambda: summarize_text(combined))
    # logging.info(f"final_summary: {final_summary}")
    # return {"summary": final_summary, "sources": used_ids}
    # 6) extractive summary
    per_article_summaries: list[str] = []
    for text in texts:
        summary = extractive_summary(text, sentences=2)
        logging.info(f"summary: {summary}")
        per_article_summaries.append(summary)
    combined = "\n".join(per_article_summaries)
    final_summary = await asyncio.to_thread(lambda: summarize_text(combined))
    # final_summary = extractive_summary(combined, sentences=5)
    return {"summary": final_summary, "sources": used_ids} 

# def summarize_long_text(text: str) -> str:
#     max_tokens = 200 

#     # tokenize once
#     tokens = tokenizer.encode(text, truncation=False)

#     # split tokens into chunks
#     chunks = [
#         tokens[i:i+max_tokens]
#         for i in range(0, len(tokens), max_tokens)
#     ]
#     logging.info(f"text has {len(chunks)} chunks")
#     chunks = chunks[:1]

#     summaries = []

#     for chunk in chunks:
#         chunk_text = tokenizer.decode(chunk, skip_special_tokens=True)

#         out = summarizer(
#             chunk_text,
#             max_length=80,
#             min_length=20,
#             do_sample=False,
#         )
#         summaries.append(out[0]["summary_text"])

#     combined = " ".join(summaries)

#     final = summarizer(
#         combined,
#         max_length=140,
#         min_length=60,
#         do_sample=False,
#     )

#     return final[0]["summary_text"]