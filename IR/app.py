from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import os
from fastapi import FastAPI, Query, HTTPException
import mysql
from cw3.backend.IR.ir_main import IRMain, QueryType

app = FastAPI(lifespan=lifespan)


@dataclass(frozen=True)
class SearchResult:
    ids: List[str]
    total: int               
    index_version: str

class IREngine:
    _index_version: str
    _ir_main: IRMain
    def __init__(self,
                  index_filepath: str,
                  documents_stat_filepath: str,
                  index_version: str = "unknown"):
        self._index_filepath = index_filepath
        self._index_version = index_version
        self.ir_main = IRMain(index_filepath, documents_stat_filepath)

    # FIXME: pass candidates
    # FIXME: str to enum
    def search_ids(self, query: str, query_type: str) -> SearchResult:
        result = self.ir_main.handle_query(query, query_type)
        return SearchResult(ids=result, total=len(result), index_version=self._index_version)


# -------------------------
# DB LAYER (interface)
# -------------------------

class DocStore:

    def __init__(self):
        self._conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
        )
    
    def fetch_docs_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join(["%s"] * len(ids))
        sql = f"""
            SELECT
              id,
              COALESCE(title, rss_title) AS headline,
              COALESCE(rss_published_at, fetched_at) AS time,
              COALESCE(final_url, url) AS url
            FROM articles
            WHERE id IN ({placeholders})
        """
        cur = self._conn.cursor(dictionary=True)
        cur.execute(sql, ids)
        rows = cur.fetchall()
        cur.close()
        return rows

    def fetch_latest(self, limit: int) -> List[Dict[str, Any]]:
        sql = """
            SELECT
              id,
              COALESCE(title, rss_title) AS headline,
              COALESCE(rss_published_at, fetched_at) AS time,
              COALESCE(final_url, url) AS url
            FROM articles
            ORDER BY COALESCE(rss_published_at, fetched_at) DESC
            LIMIT %s
        """
        cur = self._conn.cursor(dictionary=True)
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
        cur.close()
        return rows

    def fetch_candidate_ids_by_time(
        self, time_from: Optional[datetime], time_to: Optional[datetime]
    ) -> Optional[set[str]]:
        if not time_from and not time_to: 
            return None
        if time_from and time_to: 
            sql = """
                SELECT id FROM articles
                WHERE COALESCE(rss_published_at, fetched_at) BETWEEN %s AND %s
            """
            params = (time_from, time_to)
        elif time_from:
            sql = """
                SELECT id FROM articles
                WHERE COALESCE(rss_published_at, fetched_at) >= %s
            """
            params = (time_from,)
        else: 
            sql = """
                SELECT id FROM articles
                WHERE COALESCE(rss_published_at, fetched_at) <= %s
            """
            params = (time_to,)
        cur = self._conn.cursor()
        cur.execute(sql, params)
        ids = {row[0] for row in cur.fetchall()}
        cur.close()
        return ids


# -------------------------
# GLOBALS (engine + store)
# -------------------------

INDEX_VERSION = os.environ.get("INDEX_VERSION", "dev")
INDEX_PATH = os.environ.get("INDEX_PATH", "/data/index.bin")
DOCS_STAT_PATH = os.environ.get("DOCS_STAT_PATH", "/data/docs_stat.json")

# -------------------------
# STARTUP
# -------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, store
    print("Starting search service...")
    app.state.store = DocStore()  
    app.state.engine = IREngine(index_filepath=INDEX_PATH,
                                documents_stat_filepath= DOCS_STAT_PATH,
                                index_version=INDEX_VERSION)
    yield
    print("Shutting down search service")


# -------------------------
# ENDPOINTS
# -------------------------

@app.get("/health")
def health():
    engine = app.state.engine
    return {"ok": True, "index_version": engine._index_version if engine else None}


@app.get("/index_version")
def index_version():
    engine = app.state.engine
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not loaded")
    return {"version": engine._index_version}


@app.get("/search")
def search(
    query: str = Query(..., min_length=1),
    query_type: str = "FreeText",
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    time_from: Optional[datetime] = None,
    time_to: Optional[datetime] = None,
):
    """
    Returns ranked results. IR gives ids; then fetch metadata from DB.
    """
    engine = app.state.engine
    store = app.state.store
    if not engine or not store:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Snapshot the engine for consistency during reloads
    engine_snapshot = engine
    store_snapshot = store

    # Optional: pre-filter candidates by time
    candidate_ids = store_snapshot.fetch_candidate_ids_by_time(time_from, time_to)

    # Search (returns ids only)
    sr = engine_snapshot.search_ids(query, query_type, candidate_ids=candidate_ids)

    # Pagination slice
    page_ids = sr.ids[offset : offset + limit]

    # Fetch metadata for these ids
    docs = store_snapshot.fetch_docs_by_ids(page_ids)

    # Preserve ranking order
    by_id = {d["id"]: d for d in docs}
    ordered = [by_id[i] for i in page_ids if i in by_id]

    return {
        "query": query,
        "offset": offset,
        "limit": limit,
        "total": sr.total,
        "index_version": sr.index_version,
        "results": ordered,
        "has_more": offset + limit < sr.total,
    }


@app.get("/news/latest")
def latest(
    limit: int = Query(10, ge=1, le=50),
):
    store = app.state.store
    if not store:
        raise HTTPException(status_code=503, detail="Service not ready")
    docs = store.fetch_latest(limit)
    return {"results": docs}
