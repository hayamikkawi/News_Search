from __future__ import annotations
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import os
import asyncio
from fastapi import FastAPI, Query, HTTPException
from IR.helpers.doc_store import DocStore
from IR.ir.ir_main import IRMain, QueryType
from common_utils.types import DocID
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import logging
from IR.routers.summarizer import router as summarize_router

logger = logging.getLogger("search")
logging.basicConfig(level=logging.INFO)
load_dotenv()

@dataclass(frozen=True)
class SearchResult:
    ids: List[DocID]
    total: int               
    index_version: str

# -------------------------
# GLOBALS
# -------------------------
ORIGINS = [os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")]

# -------------------------
# STARTUP
# -------------------------

def load_engine_from_version(base_dir: str, version: str) -> IRMain:
    vdir = Path(base_dir) / version
    logging.info(f"vdir: {vdir}")
    index_path = str(vdir / app.state.index_filename)
    logging.info(f"index_path: {index_path}")
    stats_path = str(vdir / app.state.docs_stat_filename)
    logging.info(f"stats_path: {stats_path}")
    return IRMain(index_path, stats_path)


async def relaod_loop(app, every_seconds: int = 7200):
    logging.info("relaod_loop called")
    base_dir = app.state.index_base_dir
    latest_file = Path(base_dir) / "LATEST.txt"
    while not app.state.stop_event.is_set(): 
        logging.info("relaod_loop inside while loop")
        try:
            if latest_file.exists(): 
                latest_version = latest_file.read_text(encoding="utf-8").strip()
                logging.info(f"Latest version is: {latest_version}")
            if latest_version and latest_version != app.state.index_version: 
                logger.info("Reloading index to %s", latest_version)
                new_engine = load_engine_from_version(base_dir, latest_version)
                app.state.engine = new_engine
                app.state.index_version = latest_version
                logger.info("Index switched to %s", latest_version)
        except Exception as e: 
            logger.exception("Index reload failed (keeping current index)")
        await asyncio.sleep(every_seconds)

    

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, store
    print("Starting search service...")
    # config
    app.state.index_base_dir = os.environ.get("INDEX_BASE_DIR", "/opt/ttds-project/shared/indexer/output")
    app.state.index_filename = os.environ.get("INDEX_FILENAME", "index.txt")
    app.state.docs_stat_filename = os.environ.get("DOCS_STAT_FILENAME", "documents_stats.json")
    app.state.index_version = "boot"
    # datastore
    app.state.store = DocStore() 
    # Load the index from latest version
    latest = (Path(app.state.index_base_dir) / "LATEST.txt").read_text().strip()
    print(f"latest: {latest}")
    app.state.engine = load_engine_from_version(app.state.index_base_dir, latest)
    app.state.index_version = latest
    # reload loop
    app.state.stop_event = asyncio.Event()
    app.state.reload_task = asyncio.create_task(relaod_loop(app, every_seconds=7200))
    yield
    # shutdown
    app.state.stop_event.set()
    app.state.reload_task.cancel()
    print("Shutting down search service")

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(summarize_router)

# -------------------------
# ENDPOINTS
# -------------------------

@app.get("/health")
def health():
    engine = app.state.engine
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not loaded")
    return {"ok": True, "index_version": app.state.index_version}


@app.get("/index_version")
def index_version():
    engine = app.state.engine
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not loaded")
    return {"version": app.state.index_version}


@app.get("/search")
def search(
    query: str = Query(..., min_length=1),
    query_type: QueryType = QueryType.free_text,
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
        logger.exception("Service not ready")
        raise HTTPException(status_code=503, detail="Service not ready")
    if len(query) <= 0 or offset < 0: 
        raise HTTPException(status_code=503, detail="Bad request")
    logger.info(f"""query: {query}\n query type: {query_type}\n limit: {limit}, offset:{offset}, time from: {time_from}, time to: {time_to}""")
    # Snapshot the engine for consistency during reloads
    engine_snapshot = engine
    store_snapshot = store
    try: 
        # pre-filter candidates by time
        candidate_ids = store_snapshot.fetch_candidate_ids_by_time(time_from, time_to)

        # Search (returns ids only)
        ids = engine_snapshot.handle_query(query, query_type, candidate_ids=candidate_ids)
        sr = SearchResult(ids=ids, total=len(ids), index_version=app.state.index_version)
        # Pagination slice
        page_ids = sr.ids[offset : offset + limit]

        # Fetch metadata for these ids
        docs = store_snapshot.fetch_docs_by_ids(page_ids)
    except Exception as e:
        logger.exception(f"Search pipeline failed, {e}")
        raise HTTPException(status_code=500, detail="Internal search error")

    # Preserve ranking order
    by_id = {d["id"]: d for d in docs}
    ordered = [by_id[i] for i in page_ids if i in by_id]

    return {
        "query": query,
        "offset": offset,
        "limit": limit,
        "total": sr.total,
        "index_version": app.state.index_version,
        "results": ordered,
        "has_more": offset + limit < sr.total,
    }


@app.get("/news/latest")
def latest(limit: int = Query(10, ge=1, le=50),):
    store = app.state.store
    if not store:
        logger.exception("Service not ready")
        raise HTTPException(status_code=503, detail="Service not ready")
    
    try:
        docs = store.fetch_latest(limit)
        return {"results": docs}
    except Exception as e: 
        logger.exception(f"Fetching latest news failed, {e}")
        raise HTTPException(status_code=500, detail="Internal search error")