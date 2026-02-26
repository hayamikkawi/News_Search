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
    from src.config import MYSQL_CONFIG
    from src.storage.db_mysql import create_mysql_db
    from src.integration.indexer_interface import FileBasedIndexer
    from src.integration.coordinator import create_coordinator, CrawlerCoordinator
    from src.core.models import ArticleRecord
except ImportError as e:
    try:
        from config import MYSQL_CONFIG
        from storage.db_mysql import create_mysql_db
        from integration.indexer_interface import FileBasedIndexer
        from integration.coordinator import create_coordinator, CrawlerCoordinator
        from core.models import ArticleRecord
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
        content = json_obj.get("content", "")
        title = json_obj.get("title", "")

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


def main():
    parser = argparse.ArgumentParser(description="Import JSON data using crawler coordinator")

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--input", "-i", help="Path to input JSON array file")
    source_group.add_argument("--retry-failed", help="Path to failed JSONL file to retry")

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
    parser.set_defaults(save_content=True)

    args = parser.parse_args()

    input_file: Optional[Path] = None
    retry_failed_file: Optional[Path] = None

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
