#!/usr/bin/env python3
"""
Import large JSON file (250MB+) into MySQL database (articles table).

This script reads a JSON file containing news articles and imports them into
the MySQL database using the existing crawler database utilities.

Features:
- Streaming JSON parsing for large files (250MB+)
- Batch inserts for performance
- Progress reporting and error handling
- Duplicate URL handling (skip/update based on existing logic)
- Configurable batch size and connection settings

Usage:
    python import_json_to_mysql.py --input /path/to/news.json [--batch-size 1000] [--dry-run]
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "crawler" / "src"))

try:
    from crawler.src.storage.db_mysql import MySQLDatabase
    from crawler.src.core.models import ArticleRecord
    from crawler.src.config import MYSQL_CONFIG
except ImportError as e:
    # Try alternative import path
    try:
        from storage.db_mysql import MySQLDatabase
        from core.models import ArticleRecord
        from config import MYSQL_CONFIG
    except ImportError:
        print(f"Error importing crawler modules: {e}")
        print("Make sure you're running from the correct directory and the crawler module is available")
        print(f"Project root: {project_root}")
        print(f"Python path: {sys.path}")
        sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JSONImporter:
    """Import JSON data into MySQL database."""

    def __init__(
        self,
        db: MySQLDatabase,
        batch_size: int = 1000,
        dry_run: bool = False
    ):
        """
        Initialize the importer.

        Args:
            db: MySQLDatabase instance
            batch_size: Number of records to insert in each batch
            dry_run: If True, don't actually insert into database
        """
        self.db = db
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'duplicates': 0,
            'batches': 0
        }

    def map_json_to_article(self, json_obj: Dict[str, Any]) -> ArticleRecord:
        """
        Map JSON object to ArticleRecord.

        Mapping:
        - JSON `url` → database `url` and `final_url`
        - JSON `date` → database `rss_published_at` and `published_date`
        - JSON `content` → database `text_content`
        - JSON `title` → database `title`

        Default values:
        - `feed_url` = NULL
        - `rss_title` = NULL
        - `fetched_at` = current time
        - `http_status` = 200
        - `error` = NULL
        - `author` = NULL
        - `language` = NULL
        """
        # Extract fields from JSON
        url = json_obj.get('url', '')
        date_str = json_obj.get('date')
        content = json_obj.get('content', '')
        title = json_obj.get('title', '')

        # Parse date if available
        rss_published_at = None
        published_date = None
        if date_str:
            try:
                # Try to parse ISO format date
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                rss_published_at = dt.isoformat()
                published_date = date_str  # Keep original string
            except (ValueError, AttributeError):
                # If parsing fails, keep as string
                rss_published_at = date_str
                published_date = date_str

        # Create extracted dictionary
        extracted = {
            'title': title,
            'author': None,  # Default
            'date': published_date,
            'language': None,  # Default
            'text': content
        }

        # Create ArticleRecord
        article = ArticleRecord(
            url=url,
            final_url=url,  # Same as url
            feed_url=None,  # Default
            rss_title=None,  # Default
            rss_published_at=rss_published_at,
            fetched_at=datetime.now().isoformat(),  # Current time
            http_status=200,  # Default
            error=None,  # Default
            extracted=extracted
        )

        return article

    def stream_json_file(self, filepath: Path) -> Generator[Dict[str, Any], None, None]:
        """
        Stream JSON array from file one object at a time.

        This is memory-efficient for large JSON files.

        Args:
            filepath: Path to JSON file

        Yields:
            JSON objects from the array
        """
        logger.info(f"Opening JSON file: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            # Read opening bracket
            char = f.read(1)
            if char != '[':
                raise ValueError("JSON file must start with '[' (array)")

            # Read objects one by one
            buffer = ''
            depth = 0
            in_string = False
            escape = False

            while True:
                chunk = f.read(8192)  # 8KB chunks
                if not chunk:
                    break

                for char in chunk:
                    if escape:
                        escape = False
                        buffer += char
                    elif char == '\\':
                        escape = True
                        buffer += char
                    elif char == '"' and not in_string:
                        in_string = True
                        buffer += char
                    elif char == '"' and in_string:
                        in_string = False
                        buffer += char
                    elif char == '{' and not in_string:
                        depth += 1
                        buffer += char
                    elif char == '}' and not in_string:
                        depth -= 1
                        buffer += char
                        if depth == 0:
                            # Complete object
                            try:
                                obj = json.loads(buffer)
                                yield obj
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse JSON object: {e}")
                            buffer = ''
                    elif char == ',' and depth == 0 and not in_string:
                        # Between objects, ignore
                        continue
                    elif char == ']' and depth == 0 and not in_string:
                        # End of array
                        return
                    else:
                        buffer += char

        # Check for any remaining buffer
        if buffer.strip():
            logger.warning(f"Unprocessed buffer at end of file: {buffer[:100]}...")

    def process_batch(self, articles: List[ArticleRecord]) -> None:
        """
        Process a batch of articles.

        Args:
            articles: List of ArticleRecord objects
        """
        if self.dry_run:
            logger.info(f"DRY RUN: Would insert {len(articles)} articles")
            self.stats['success'] += len(articles)
            return

        batch_start_time = time.time()
        success_count = 0

        for article in articles:
            try:
                result = self.db.save_article(article)
                if result:
                    success_count += 1
                else:
                    self.stats['failed'] += 1
                    logger.warning(f"Failed to save article: {article.url}")
            except Exception as e:
                self.stats['failed'] += 1
                logger.error(f"Error saving article {article.url}: {e}")

        batch_time = time.time() - batch_start_time
        logger.info(f"Batch processed: {success_count}/{len(articles)} articles in {batch_time:.2f}s "
                   f"({len(articles)/batch_time:.1f} articles/sec)")

        self.stats['success'] += success_count
        self.stats['batches'] += 1

    def import_file(self, filepath: Path) -> None:
        """
        Import JSON file into database.

        Args:
            filepath: Path to JSON file
        """
        logger.info(f"Starting import from {filepath}")
        logger.info(f"Batch size: {self.batch_size}, Dry run: {self.dry_run}")

        start_time = time.time()
        current_batch = []

        try:
            for i, json_obj in enumerate(self.stream_json_file(filepath), 1):
                self.stats['total'] += 1

                # Map JSON to ArticleRecord
                try:
                    article = self.map_json_to_article(json_obj)
                    current_batch.append(article)
                except Exception as e:
                    self.stats['failed'] += 1
                    logger.error(f"Error mapping JSON object {i}: {e}")
                    continue

                # Process batch when full
                if len(current_batch) >= self.batch_size:
                    self.process_batch(current_batch)
                    current_batch = []

                # Progress reporting
                if i % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    logger.info(f"Processed {i} records, {rate:.1f} records/sec")

            # Process remaining batch
            if current_batch:
                self.process_batch(current_batch)

        except Exception as e:
            logger.error(f"Error during import: {e}")
            raise

        finally:
            # Print summary
            total_time = time.time() - start_time
            self.print_summary(total_time)

    def print_summary(self, total_time: float) -> None:
        """Print import summary statistics."""
        logger.info("=" * 60)
        logger.info("IMPORT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total records processed: {self.stats['total']}")
        logger.info(f"Successfully inserted: {self.stats['success']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Duplicates handled: {self.stats.get('duplicates', 0)}")
        logger.info(f"Batches processed: {self.stats['batches']}")
        logger.info(f"Total time: {total_time:.2f} seconds")

        if self.stats['total'] > 0:
            rate = self.stats['total'] / total_time
            logger.info(f"Processing rate: {rate:.1f} records/second")

        if self.dry_run:
            logger.info("DRY RUN: No data was actually inserted into database")
        logger.info("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import JSON file into MySQL database"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("/home/xinleeds_gmail_com/tmp_main/web-searcher/indexer/input/news.json"),
        help="Path to input JSON file"
    )
    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=1000,
        help="Batch size for database inserts (default: 1000)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (don't insert into database)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=MYSQL_CONFIG.host,
        help=f"MySQL host (default: {MYSQL_CONFIG.host})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=MYSQL_CONFIG.port,
        help=f"MySQL port (default: {MYSQL_CONFIG.port})"
    )
    parser.add_argument(
        "--user",
        type=str,
        default=MYSQL_CONFIG.user,
        help=f"MySQL user (default: {MYSQL_CONFIG.user})"
    )
    parser.add_argument(
        "--password",
        type=str,
        default=MYSQL_CONFIG.password,
        help=f"MySQL password (default: {MYSQL_CONFIG.password})"
    )
    parser.add_argument(
        "--database",
        type=str,
        default=MYSQL_CONFIG.database,
        help=f"MySQL database (default: {MYSQL_CONFIG.database})"
    )

    args = parser.parse_args()

    # Check if input file exists
    if not args.input.exists():
        logger.error(f"Input file does not exist: {args.input}")
        sys.exit(1)

    # Initialize database connection
    try:
        logger.info(f"Connecting to MySQL at {args.host}:{args.port}/{args.database}")
        db = MySQLDatabase(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database,
            pool_size=5
        )
        db.initialize_pool()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)

    # Create and run importer
    importer = JSONImporter(
        db=db,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

    try:
        importer.import_file(args.input)
    except KeyboardInterrupt:
        logger.info("Import interrupted by user")
        importer.print_summary(time.time() - time.time())
    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)
    finally:
        logger.info("Import completed")


if __name__ == "__main__":
    main()