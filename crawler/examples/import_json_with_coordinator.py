#!/usr/bin/env python3
"""
Import large JSON file (250MB+) using the crawler coordinator.

This script reads a JSON file containing news articles, converts them to ArticleRecord objects,
and processes them through the coordinator which:
1. Stores metadata to MySQL database
2. Sends content to FileBasedIndexer
3. Saves content back to database (enabled by default)

Supports:
- Streaming JSON parsing for large files
- Retry mode from failed JSONL records
- Optional skip-existing check against DB (url + feed_url)
- Failed record output for post-mortem and retry
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator, Tuple, Set

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

try:
    from src.config import MYSQL_CONFIG, CONFIG
    from src.storage.db_mysql import create_mysql_db
    from src.integration.indexer_interface import FileBasedIndexer
    from src.integration.coordinator import create_coordinator, CrawlerCoordinator
    from src.core.models import ArticleRecord
    from src.core.fetcher import build_session, fetch_html
    from src.core.extractor import extract_main_text
except ImportError as e:
    try:
        from config import MYSQL_CONFIG, CONFIG
        from storage.db_mysql import create_mysql_db
        from integration.indexer_interface import FileBasedIndexer
        from integration.coordinator import create_coordinator, CrawlerCoordinator
        from core.models import ArticleRecord
        from core.fetcher import build_session, fetch_html
        from core.extractor import extract_main_text
    except ImportError:
        print(f"Error importing crawler modules: {e}")
        print("Make sure you're running from the correct directory and the crawler module is available")
        print(f"Project root: {project_root}")
        print(f"Python path: {sys.path}")
        sys.exit(1)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

COMMONCRAWL_FEED_URL = "https://data.commoncrawl.org"


class JSONStreamProcessor:
    """Process JSON file with streaming parser and coordinator integration."""

    def __init__(
        self,
        coordinator: Optional[CrawlerCoordinator],
        batch_size: int = 1000,
        dry_run: bool = False,
        save_content_to_db: bool = True,
        failed_output_path: Optional[Path] = None,
        skip_existing: bool = False,
    ):
        self.coordinator = coordinator
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.save_content_to_db = save_content_to_db
        self.failed_output_path = failed_output_path
        self.skip_existing = skip_existing
        self._existing_cache: Dict[str, bool] = {}

        self.stats = {
            "total": 0,
            "processed": 0,
            "failed": 0,
            "duplicates": 0,
            "batches": 0,
            "metadata_saved": 0,
            "indexer_sent": 0,
            "content_saved": 0,
            "skipped_existing": 0,
        }
        self.failed_records_written = 0

    def map_json_to_article(self, json_obj: Dict[str, Any]) -> ArticleRecord:
        url = json_obj.get("url", "")
        date_str = json_obj.get("date")
        # Compatible with both schemas:
        # - old: content/title
        # - new: text/headline
        content = json_obj.get("content") or json_obj.get("text", "")
        title = json_obj.get("title") or json_obj.get("headline", "")

        rss_published_at = None
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                rss_published_at = dt.isoformat()
            except (ValueError, AttributeError):
                rss_published_at = date_str

        extracted = {
            "title": title,
            "author": None,
            "date": date_str,
            "language": None,
            "description": None,
            "text": content,
            "text_ok": True,
        }

        return ArticleRecord(
            url=url,
            final_url=url,
            feed_url=COMMONCRAWL_FEED_URL,
            rss_title=None,
            rss_published_at=rss_published_at,
            fetched_at=datetime.now().isoformat(),
            http_status=200,
            error=None,
            extracted=extracted,
        )

    def _write_failed_record(self, payload: Dict[str, Any]) -> None:
        if not self.failed_output_path:
            return
        self.failed_output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.failed_output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.failed_records_written += 1

    def _chunked(self, values: List[str], chunk_size: int = 500) -> Generator[List[str], None, None]:
        for i in range(0, len(values), chunk_size):
            yield values[i:i + chunk_size]

    def _filter_existing_batch(
        self, batch: List[Tuple[int, Dict[str, Any], ArticleRecord]]
    ) -> List[Tuple[int, Dict[str, Any], ArticleRecord]]:
        """
        Batch reconcile by querying existing (url, feed_url) once per chunk.
        Much faster than per-row SELECT.
        """
        if self.dry_run or not self.coordinator or not batch:
            return batch

        # Group by feed_url to keep SQL simple and index-friendly
        grouped_urls: Dict[str, Set[str]] = {}
        for _, _, article in batch:
            if article.url:
                grouped_urls.setdefault(article.feed_url, set()).add(article.url)

        existing_keys: Set[str] = set()
        try:
            with self.coordinator.database.get_connection() as conn:
                cursor = conn.cursor()
                for feed_url, url_set in grouped_urls.items():
                    urls = list(url_set)
                    for url_chunk in self._chunked(urls, chunk_size=500):
                        placeholders = ",".join(["%s"] * len(url_chunk))
                        sql = (
                            f"SELECT url FROM articles WHERE feed_url = %s "
                            f"AND url IN ({placeholders})"
                        )
                        params = [feed_url] + url_chunk
                        cursor.execute(sql, params)
                        rows = cursor.fetchall()
                        for row in rows:
                            existing_keys.add(f"{feed_url}|{row[0]}")
                cursor.close()
        except Exception as e:
            logger.warning(f"Batch existence check failed, fallback to no-skip for this batch: {e}")
            return batch

        filtered: List[Tuple[int, Dict[str, Any], ArticleRecord]] = []
        skipped = 0
        for item in batch:
            _, _, article = item
            key = f"{article.feed_url}|{article.url}"
            if key in existing_keys:
                skipped += 1
                continue
            filtered.append(item)

        if skipped:
            self.stats["skipped_existing"] += skipped
            logger.info(f"Batch reconcile: skipped {skipped} existing rows")
        return filtered

    def stream_json_file(self, filepath: Path) -> Generator[Dict[str, Any], None, None]:
        logger.info(f"Opening JSON file: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            char = f.read(1)
            if char != "[":
                raise ValueError("JSON file must start with '[' (array)")

            buffer = ""
            depth = 0
            in_string = False
            escape = False

            while True:
                chunk = f.read(8192)
                if not chunk:
                    break

                for char in chunk:
                    if escape:
                        escape = False
                        buffer += char
                    elif char == "\\":
                        escape = True
                        buffer += char
                    elif char == '"' and not in_string:
                        in_string = True
                        buffer += char
                    elif char == '"' and in_string:
                        in_string = False
                        buffer += char
                    elif char == "{" and not in_string:
                        depth += 1
                        buffer += char
                    elif char == "}" and not in_string:
                        depth -= 1
                        buffer += char
                        if depth == 0:
                            try:
                                obj = json.loads(buffer)
                                yield obj
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse JSON object: {e}\\nBuffer: {buffer[:200]}...")
                            buffer = ""
                    elif char == "," and depth == 0 and not in_string:
                        continue
                    else:
                        buffer += char

            if buffer.strip() and buffer.strip() != "]":
                logger.warning(f"Trailing content in JSON file: {buffer[:100]}...")

    def stream_failed_jsonl(self, filepath: Path) -> Generator[Dict[str, Any], None, None]:
        logger.info(f"Opening failed-record JSONL file: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON at failed-file line {lineno}: {e}")
                    continue

                if isinstance(obj, dict) and isinstance(obj.get("raw"), dict):
                    yield obj["raw"]
                elif isinstance(obj, dict):
                    yield obj
                else:
                    logger.warning(f"Unsupported payload at failed-file line {lineno}, skipping")

    def process_file(self, input_file: Optional[Path], retry_failed_file: Optional[Path] = None) -> bool:
        source_desc = str(retry_failed_file) if retry_failed_file else str(input_file)
        logger.info(f"Starting processing of {source_desc}")
        logger.info(
            f"Batch size: {self.batch_size}, Dry run: {self.dry_run}, "
            f"save_content_to_db: {self.save_content_to_db}, skip_existing: {self.skip_existing}"
        )

        batch: List[Tuple[int, Dict[str, Any], ArticleRecord]] = []
        start_time = time.time()

        try:
            if retry_failed_file:
                source_iter = self.stream_failed_jsonl(retry_failed_file)
            else:
                if input_file is None:
                    raise ValueError("input_file is required when retry_failed_file is not provided")
                source_iter = self.stream_json_file(input_file)

            for i, json_obj in enumerate(source_iter):
                self.stats["total"] += 1

                try:
                    article = self.map_json_to_article(json_obj)

                    batch.append((i + 1, json_obj, article))

                    if len(batch) >= self.batch_size:
                        self._process_batch(batch)
                        batch = []

                except Exception as e:
                    self.stats["failed"] += 1
                    logger.error(f"Error processing record {i+1}: {e}")
                    self._write_failed_record(
                        {
                            "record_index": i + 1,
                            "url": json_obj.get("url") if isinstance(json_obj, dict) else None,
                            "stage": "map_json_to_article",
                            "error": str(e),
                            "raw": json_obj,
                        }
                    )
                    continue

                if (i + 1) % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    logger.info(f"Processed {i+1} records ({rate:.1f} records/sec)")

            if batch:
                self._process_batch(batch)

            elapsed = time.time() - start_time
            logger.info("=" * 70)
            logger.info("PROCESSING COMPLETE")
            logger.info("=" * 70)
            logger.info(f"Total records: {self.stats['total']}")
            logger.info(f"Processed batches: {self.stats['batches']}")
            logger.info(f"Metadata saved: {self.stats['metadata_saved']}")
            logger.info(f"Sent to indexer: {self.stats['indexer_sent']}")
            logger.info(f"Content saved to DB: {self.stats['content_saved']}")
            logger.info(f"Skipped existing: {self.stats['skipped_existing']}")
            logger.info(f"Failed: {self.stats['failed']}")
            logger.info(f"Failed records written: {self.failed_records_written}")
            logger.info(f"Elapsed time: {elapsed:.2f} seconds")
            logger.info(f"Processing rate: {self.stats['total']/elapsed:.1f} records/sec" if elapsed > 0 else "N/A")

            if not self.dry_run and self.coordinator:
                db_ok, indexer_ok = self.coordinator.check_health()
                logger.info(f"Health check - Database: {'OK' if db_ok else 'FAILED'}, Indexer: {'OK' if indexer_ok else 'FAILED'}")

            return True

        except Exception as e:
            logger.error(f"Fatal error processing file: {e}")
            return False

    def _process_batch(self, batch: List[Tuple[int, Dict[str, Any], ArticleRecord]]):
        if self.dry_run:
            logger.info(f"DRY RUN: Would process batch of {len(batch)} articles")
            self.stats["batches"] += 1
            self.stats["metadata_saved"] += len(batch)
            self.stats["indexer_sent"] += len(batch)
            if self.save_content_to_db:
                self.stats["content_saved"] += len(batch)
            return

        try:
            if self.skip_existing:
                batch = self._filter_existing_batch(batch)
                if not batch:
                    self.stats["batches"] += 1
                    logger.info("Batch reconcile: all rows already exist, skipping coordinator/indexer")
                    return

            logger.info(f"Processing batch of {len(batch)} articles...")
            articles = [item[2] for item in batch]
            results = self.coordinator.process_articles_batch(articles)

            self.stats["batches"] += 1
            self.stats["metadata_saved"] += sum(1 for r in results if r.metadata_saved)
            self.stats["indexer_sent"] += sum(1 for r in results if r.indexer_sent)
            self.stats["content_saved"] += sum(1 for r in results if r.content_saved)
            self.stats["failed"] += sum(1 for r in results if r.error is not None)
            self.stats["processed"] += len(batch)

            for (record_index, raw_obj, article), result in zip(batch, results):
                if result.error is not None:
                    self._write_failed_record(
                        {
                            "record_index": record_index,
                            "url": article.url,
                            "stage": "coordinator.process_articles_batch",
                            "error": result.error,
                            "doc_id": result.doc_id,
                            "metadata_saved": result.metadata_saved,
                            "indexer_sent": result.indexer_sent,
                            "content_saved": result.content_saved,
                            "raw": raw_obj,
                        }
                    )

            logger.info(f"Batch completed: {len(batch)} articles, {sum(1 for r in results if r.error is not None)} errors")

        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            self.stats["failed"] += len(batch)
            for record_index, raw_obj, article in batch:
                self._write_failed_record(
                    {
                        "record_index": record_index,
                        "url": article.url,
                        "stage": "process_batch_exception",
                        "error": str(e),
                        "raw": raw_obj,
                    }
                )


class DBIncrementalExporter:
    """Export non-CommonCrawl articles from DB in incremental files for indexer format."""

    def __init__(
        self,
        coordinator: CrawlerCoordinator,
        state_file: Path,
        failed_output_path: Optional[Path],
        repair_null_text: bool = True,
        repair_min_text_length: int = 400,
    ):
        self.coordinator = coordinator
        self.state_file = state_file
        self.failed_output_path = failed_output_path
        self.repair_null_text = repair_null_text
        self.repair_min_text_length = repair_min_text_length
        self.failed_records_written = 0
        self.session = build_session()

    def _write_failed_record(self, payload: Dict[str, Any]) -> None:
        if not self.failed_output_path:
            return
        self.failed_output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.failed_output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.failed_records_written += 1

    def _read_last_exported_id(self) -> int:
        if not self.state_file.exists():
            return 0
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            value = int(data.get("last_exported_id", 0))
            return max(0, value)
        except Exception as e:
            logger.warning(f"Failed to read state file {self.state_file}, fallback to 0: {e}")
            return 0

    def _write_last_exported_id(self, value: int) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_exported_id": int(value),
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _get_max_incremental_id(self, last_exported_id: int) -> int:
        with self.coordinator.database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT MAX(id)
                    FROM articles
                    WHERE id > %s
                      AND (feed_url IS NULL OR feed_url <> %s)
                    """,
                    (last_exported_id, COMMONCRAWL_FEED_URL),
                )
                row = cursor.fetchone()
                return int(row[0]) if row and row[0] else 0
            finally:
                cursor.close()

    def _get_rows_with_null_text(self, last_exported_id: int, max_id: int) -> List[Dict[str, Any]]:
        with self.coordinator.database.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT id, url, final_url
                    FROM articles
                    WHERE id > %s AND id <= %s
                      AND (feed_url IS NULL OR feed_url <> %s)
                      AND text_content IS NULL
                    ORDER BY id ASC
                    """,
                    (last_exported_id, max_id, COMMONCRAWL_FEED_URL),
                )
                return cursor.fetchall()
            finally:
                cursor.close()

    def _get_exportable_rows(self, last_exported_id: int, max_id: int) -> List[Dict[str, Any]]:
        with self.coordinator.database.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT id, title, text_content
                    FROM articles
                    WHERE id > %s AND id <= %s
                      AND (feed_url IS NULL OR feed_url <> %s)
                      AND text_content IS NOT NULL
                      AND text_content <> ''
                    ORDER BY id ASC
                    """,
                    (last_exported_id, max_id, COMMONCRAWL_FEED_URL),
                )
                return cursor.fetchall()
            finally:
                cursor.close()

    def _repair_null_text_content(self, rows: List[Dict[str, Any]]) -> Tuple[int, int]:
        repaired = 0
        failed = 0
        for row in rows:
            doc_id = row["id"]
            target_url = row.get("final_url") or row.get("url")

            if not target_url:
                failed += 1
                self._write_failed_record(
                    {
                        "doc_id": doc_id,
                        "url": row.get("url"),
                        "final_url": row.get("final_url"),
                        "stage": "repair_null_text_content",
                        "error": "Both final_url and url are empty",
                    }
                )
                continue

            try:
                fetch = fetch_html(
                    session=self.session,
                    url=target_url,
                    user_agent=CONFIG.user_agent,
                    timeout_seconds=CONFIG.timeout_seconds,
                )
                if not fetch.ok or not fetch.html:
                    failed += 1
                    self._write_failed_record(
                        {
                            "doc_id": doc_id,
                            "url": row.get("url"),
                            "final_url": row.get("final_url"),
                            "stage": "repair_null_text_content.fetch",
                            "error": fetch.error or f"http_status={fetch.status}",
                        }
                    )
                    continue

                extracted = extract_main_text(
                    fetch.html,
                    fetch.final_url or target_url,
                    min_text_length=self.repair_min_text_length,
                )
                text = extracted.text if extracted and extracted.text_ok else None
                if not text:
                    failed += 1
                    self._write_failed_record(
                        {
                            "doc_id": doc_id,
                            "url": row.get("url"),
                            "final_url": row.get("final_url"),
                            "stage": "repair_null_text_content.extract",
                            "error": "extract_too_short_or_empty",
                        }
                    )
                    continue

                if self.coordinator.database.update_article_content(doc_id, text):
                    repaired += 1
                else:
                    failed += 1
                    self._write_failed_record(
                        {
                            "doc_id": doc_id,
                            "url": row.get("url"),
                            "final_url": row.get("final_url"),
                            "stage": "repair_null_text_content.update",
                            "error": "update_article_content_failed",
                        }
                    )
            except Exception as e:
                failed += 1
                self._write_failed_record(
                    {
                        "doc_id": doc_id,
                        "url": row.get("url"),
                        "final_url": row.get("final_url"),
                        "stage": "repair_null_text_content.exception",
                        "error": str(e),
                    }
                )

        return repaired, failed

    def run(self) -> bool:
        last_exported_id = self._read_last_exported_id()
        logger.info(f"DB incremental export starts from last_exported_id={last_exported_id}")

        max_id = self._get_max_incremental_id(last_exported_id)
        if max_id <= last_exported_id:
            logger.info("No new non-commoncrawl rows to export")
            return True

        logger.info(f"Detected incremental id range: ({last_exported_id}, {max_id}]")

        if self.repair_null_text:
            null_rows = self._get_rows_with_null_text(last_exported_id, max_id)
            logger.info(f"Rows with NULL text_content in incremental range: {len(null_rows)}")
            repaired, failed = self._repair_null_text_content(null_rows)
            logger.info(
                f"NULL text_content repair done: repaired={repaired}, failed={failed}, "
                f"failed_records_written={self.failed_records_written}"
            )

        rows = self._get_exportable_rows(last_exported_id, max_id)
        logger.info(f"Exportable rows in incremental range: {len(rows)}")

        for row in rows:
            doc_id = int(row["id"])
            content = row.get("text_content") or ""
            metadata = {
                "title": row.get("title") or "",
                "description": None,
            }
            ok = self.coordinator.indexer.send_document(doc_id=doc_id, content=content, metadata=metadata)
            if not ok:
                self._write_failed_record(
                    {
                        "doc_id": doc_id,
                        "stage": "db_incremental_export.send_document",
                        "error": "send_document_failed",
                    }
                )

        if rows:
            flush_ok = self.coordinator.indexer.flush(mode="new_file")
            if not flush_ok:
                logger.error("Failed to flush incremental docs file")
                return False
            logger.info(f"Incremental docs file created for {len(rows)} rows")
        else:
            logger.info("No exportable rows (all missing/empty text_content after repair)")

        self._write_last_exported_id(max_id)
        logger.info(f"State updated: last_exported_id={max_id}")
        return True


def main():
    parser = argparse.ArgumentParser(description="Import JSON data using crawler coordinator")

    source_group = parser.add_mutually_exclusive_group(required=False)
    source_group.add_argument("--input", "-i", help="Path to input JSON array file")
    source_group.add_argument("--retry-failed", help="Path to failed JSONL file to retry")
    source_group.add_argument(
        "--export-from-db",
        action="store_true",
        help="Export incremental non-commoncrawl rows from DB in indexer format",
    )

    parser.add_argument("--batch-size", "-b", type=int, default=1000, help="Batch size for processing")
    parser.add_argument("--skip-existing", action="store_true", help="Skip rows already existing in DB")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--save-content", dest="save_content", action="store_true", help="Save content back to DB")
    parser.add_argument("--no-save-content", dest="save_content", action="store_false", help="Do not save content back to DB")
    parser.add_argument("--output-dir", "-o", default="./output", help="Output directory for indexer JSON")
    parser.add_argument("--output-filename", default="docs.json", help="Output filename for indexer")
    parser.add_argument(
        "--failed-output",
        default="./output/import_failed_records.jsonl",
        help="JSONL path for failed records",
    )
    parser.add_argument(
        "--state-file",
        default="./output/export_state.json",
        help="State file path for DB incremental export",
    )
    parser.add_argument(
        "--repair-null-text",
        dest="repair_null_text",
        action="store_true",
        help="Repair NULL text_content in DB incremental rows before export",
    )
    parser.add_argument(
        "--no-repair-null-text",
        dest="repair_null_text",
        action="store_false",
        help="Do not repair NULL text_content before export",
    )
    parser.add_argument(
        "--repair-min-text-length",
        type=int,
        default=CONFIG.min_text_length,
        help="Minimum extracted text length for NULL text_content repair",
    )
    parser.set_defaults(save_content=True)
    parser.set_defaults(repair_null_text=True)

    args = parser.parse_args()

    input_file: Optional[Path] = None
    retry_failed_file: Optional[Path] = None
    mode_count = int(bool(args.input)) + int(bool(args.retry_failed)) + int(bool(args.export_from_db))
    if mode_count != 1:
        parser.error("Exactly one of --input, --retry-failed, or --export-from-db is required")

    if args.input:
        input_file = Path(args.input)
        if not input_file.exists():
            logger.error(f"Input file not found: {input_file}")
            sys.exit(1)

    if args.retry_failed:
        retry_failed_file = Path(args.retry_failed)
        if not retry_failed_file.exists():
            logger.error(f"Retry-failed file not found: {retry_failed_file}")
            sys.exit(1)

    if args.export_from_db and args.dry_run:
        logger.error("--dry-run is not supported with --export-from-db")
        sys.exit(1)

    logger.info("Initializing components...")

    if not args.dry_run:
        try:
            database = create_mysql_db(
                host=MYSQL_CONFIG.host,
                port=MYSQL_CONFIG.port,
                user=MYSQL_CONFIG.user,
                password=MYSQL_CONFIG.password,
                database="ttds_search_engine",
                pool_size=MYSQL_CONFIG.pool_size,
            )
            logger.info("Database initialized")

            indexer = FileBasedIndexer(
                output_dir=args.output_dir,
                output_filename=args.output_filename,
                dedup_threshold_mb=100,
            )
            logger.info(f"Indexer initialized (output: {Path(args.output_dir)/args.output_filename})")

            coordinator = create_coordinator(
                database=database,
                indexer=indexer,
                save_content_to_db=args.save_content,
            )
            logger.info(f"Coordinator initialized (save_content_to_db: {args.save_content})")

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            sys.exit(1)
    else:
        coordinator = None
        if args.skip_existing:
            logger.warning("--skip-existing is ignored in --dry-run mode")
        logger.info("DRY RUN MODE - No actual database/indexer operations")

    failed_output_path = Path(args.failed_output)
    if failed_output_path.exists() and (retry_failed_file is None or failed_output_path != retry_failed_file):
        failed_output_path.unlink()

    if args.export_from_db:
        exporter = DBIncrementalExporter(
            coordinator=coordinator,
            state_file=Path(args.state_file),
            failed_output_path=failed_output_path,
            repair_null_text=args.repair_null_text,
            repair_min_text_length=args.repair_min_text_length,
        )
        success = exporter.run()
    else:
        processor = JSONStreamProcessor(
            coordinator=coordinator,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            save_content_to_db=args.save_content,
            failed_output_path=failed_output_path,
            skip_existing=args.skip_existing,
        )
        success = processor.process_file(input_file=input_file, retry_failed_file=retry_failed_file)

    if success:
        logger.info("Import completed successfully")
        if not args.dry_run:
            logger.info(f"Indexer output created at: {Path(args.output_dir)/args.output_filename}")
    else:
        logger.error("Import failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
