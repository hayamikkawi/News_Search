#!/usr/bin/env python3
"""
Import large JSON file (250MB+) using the crawler coordinator.

This script reads a JSON file containing news articles, converts them to ArticleRecord objects,
and processes them through the coordinator which:
1. Stores metadata to MySQL database (ttds_mysql container)
2. Sends content to FileBasedIndexer to create docs.json
3. Optionally saves content back to database (disabled by default)

Features:
- Streaming JSON parsing for large files (250MB+)
- Batch processing with coordinator.process_articles_batch()
- Progress reporting and error handling
- Configurable batch size and connection settings
- Outputs docs.json in correct format for the indexer

Usage:
    python import_json_with_coordinator.py --input /path/to/news.json [--batch-size 1000] [--dry-run] [--save-content]

Requirements:
    - Existing MySQL database (ttds_mysql container)
    - Crawler coordinator components
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
sys.path.insert(0, str(project_root / "src"))

try:
    from src.config import MYSQL_CONFIG, INDEXER_CONFIG
    from src.storage.db_mysql import create_mysql_db
    from src.integration.indexer_interface import FileBasedIndexer
    from src.integration.coordinator import create_coordinator, CrawlerCoordinator
    from src.core.models import ArticleRecord
except ImportError as e:
    # Try alternative import path
    try:
        from config import MYSQL_CONFIG, INDEXER_CONFIG
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JSONStreamProcessor:
    """Process JSON file with streaming parser and coordinator integration."""

    def __init__(
        self,
        coordinator: CrawlerCoordinator,
        batch_size: int = 1000,
        dry_run: bool = False
    ):
        """
        Initialize the processor.

        Args:
            coordinator: CrawlerCoordinator instance
            batch_size: Number of records to process in each batch
            dry_run: If True, don't actually insert into database or indexer
        """
        self.coordinator = coordinator
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.stats = {
            'total': 0,
            'processed': 0,
            'failed': 0,
            'duplicates': 0,
            'batches': 0,
            'metadata_saved': 0,
            'indexer_sent': 0,
            'content_saved': 0
        }

    def map_json_to_article(self, json_obj: Dict[str, Any]) -> ArticleRecord:
        """
        Map JSON object to ArticleRecord with proper mapping.

        Mapping:
        - JSON `url` → ArticleRecord `url` and `final_url`
        - JSON `date` → ArticleRecord `rss_published_at` and extracted `date`
        - JSON `content` → extracted `text` (for indexer)
        - JSON `title` → extracted `title`
        - Set `extracted["text_ok"] = True` (required by coordinator)

        Default values:
        - `feed_url=None`
        - `fetched_at=current_time`
        - `http_status=200`
        - `error=None`
        """
        # Extract fields from JSON
        url = json_obj.get('url', '')
        date_str = json_obj.get('date')
        content = json_obj.get('content', '')
        title = json_obj.get('title', '')

        # Parse date if available
        rss_published_at = None
        if date_str:
            try:
                # Try to parse ISO format date
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                rss_published_at = dt.isoformat()
            except (ValueError, AttributeError):
                # If parsing fails, keep as string
                rss_published_at = date_str

        # Create extracted dictionary with required fields
        extracted = {
            'title': title,
            'author': None,
            'date': date_str,  # Keep original date string
            'language': None,
            'description': None,
            'text': content,
            'text_ok': True  # Required by coordinator
        }

        # Create ArticleRecord
        article = ArticleRecord(
            url=url,
            final_url=url,  # Same as url
            feed_url=None,
            rss_title=None,
            rss_published_at=rss_published_at,
            fetched_at=datetime.now().isoformat(),
            http_status=200,
            error=None,
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
                            # Complete object found
                            try:
                                obj = json.loads(buffer)
                                yield obj
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse JSON object: {e}\nBuffer: {buffer[:200]}...")
                            buffer = ''
                    elif char == ',' and depth == 0 and not in_string:
                        # Skip commas between objects
                        continue
                    else:
                        buffer += char

            # Check for trailing content
            if buffer.strip() and buffer.strip() != ']':
                logger.warning(f"Trailing content in JSON file: {buffer[:100]}...")

    def process_file(self, input_file: Path) -> bool:
        """
        Process the entire JSON file.

        Args:
            input_file: Path to input JSON file

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Starting processing of {input_file}")
        logger.info(f"Batch size: {self.batch_size}, Dry run: {self.dry_run}")

        batch = []
        start_time = time.time()

        try:
            for i, json_obj in enumerate(self.stream_json_file(input_file)):
                self.stats['total'] += 1

                try:
                    # Map JSON to ArticleRecord
                    article = self.map_json_to_article(json_obj)
                    batch.append(article)

                    # Process batch when size reached
                    if len(batch) >= self.batch_size:
                        self._process_batch(batch)
                        batch = []

                except Exception as e:
                    self.stats['failed'] += 1
                    logger.error(f"Error processing record {i+1}: {e}")
                    continue

                # Progress reporting
                if (i + 1) % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    logger.info(f"Processed {i+1} records ({rate:.1f} records/sec)")

            # Process remaining batch
            if batch:
                self._process_batch(batch)

            # Final statistics
            elapsed = time.time() - start_time
            logger.info("=" * 70)
            logger.info("PROCESSING COMPLETE")
            logger.info("=" * 70)
            logger.info(f"Total records: {self.stats['total']}")
            logger.info(f"Processed batches: {self.stats['batches']}")
            logger.info(f"Metadata saved: {self.stats['metadata_saved']}")
            logger.info(f"Sent to indexer: {self.stats['indexer_sent']}")
            logger.info(f"Content saved to DB: {self.stats['content_saved']}")
            logger.info(f"Failed: {self.stats['failed']}")
            logger.info(f"Elapsed time: {elapsed:.2f} seconds")
            logger.info(f"Processing rate: {self.stats['total']/elapsed:.1f} records/sec" if elapsed > 0 else "N/A")

            # Health check
            if not self.dry_run:
                db_ok, indexer_ok = self.coordinator.check_health()
                logger.info(f"Health check - Database: {'OK' if db_ok else 'FAILED'}, Indexer: {'OK' if indexer_ok else 'FAILED'}")

            return True

        except Exception as e:
            logger.error(f"Fatal error processing file: {e}")
            return False

    def _process_batch(self, batch: List[ArticleRecord]):
        """Process a batch of articles."""
        if self.dry_run:
            logger.info(f"DRY RUN: Would process batch of {len(batch)} articles")
            self.stats['batches'] += 1
            self.stats['metadata_saved'] += len(batch)  # Simulated
            self.stats['indexer_sent'] += len(batch)    # Simulated
            return

        try:
            logger.info(f"Processing batch of {len(batch)} articles...")
            results = self.coordinator.process_articles_batch(batch)

            # Update statistics
            self.stats['batches'] += 1
            self.stats['metadata_saved'] += sum(1 for r in results if r.metadata_saved)
            self.stats['indexer_sent'] += sum(1 for r in results if r.indexer_sent)
            self.stats['content_saved'] += sum(1 for r in results if r.content_saved)
            self.stats['failed'] += sum(1 for r in results if r.error is not None)

            logger.info(f"Batch completed: {len(batch)} articles, {sum(1 for r in results if r.error is not None)} errors")

        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            self.stats['failed'] += len(batch)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Import JSON data using crawler coordinator')
    parser.add_argument('--input', '-i', required=True,
                       help='Path to input JSON file (e.g., /path/to/news.json)')
    parser.add_argument('--batch-size', '-b', type=int, default=1000,
                       help='Batch size for processing (default: 1000)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run mode (no database or indexer operations)')
    parser.add_argument('--save-content', action='store_true',
                       help='Save content back to database (default: False)')
    parser.add_argument('--output-dir', '-o', default='./output',
                       help='Output directory for docs.json (default: ./output)')
    parser.add_argument('--output-filename', default='docs.json',
                       help='Output filename for indexer (default: docs.json)')

    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        sys.exit(1)

    # Initialize components
    logger.info("Initializing components...")

    if not args.dry_run:
        try:
            # Initialize database
            database = create_mysql_db(
                host=MYSQL_CONFIG.host,
                port=MYSQL_CONFIG.port,
                user=MYSQL_CONFIG.user,
                password=MYSQL_CONFIG.password,
                # database=MYSQL_CONFIG.database,
                database="test_db",  # Use test database to avoid affecting production data
                pool_size=MYSQL_CONFIG.pool_size,
            )
            logger.info("Database initialized")

            # Initialize indexer
            indexer = FileBasedIndexer(
                output_dir=args.output_dir,
                output_filename=args.output_filename,
                dedup_threshold_mb=100
            )
            logger.info(f"Indexer initialized (output: {Path(args.output_dir)/args.output_filename})")

            # Create coordinator
            coordinator = create_coordinator(
                database=database,
                indexer=indexer,
                save_content_to_db=args.save_content
            )
            logger.info(f"Coordinator initialized (save_content_to_db: {args.save_content})")

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            sys.exit(1)
    else:
        # Dry run - use dummy coordinator
        coordinator = None
        logger.info("DRY RUN MODE - No actual database/indexer operations")

    # Create processor
    processor = JSONStreamProcessor(
        coordinator=coordinator,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

    # Process file
    success = processor.process_file(input_file)

    if success:
        logger.info("Import completed successfully")
        if not args.dry_run:
            logger.info(f"Indexer output created at: {Path(args.output_dir)/args.output_filename}")
    else:
        logger.error("Import failed")
        sys.exit(1)


if __name__ == '__main__':
    main()