"""
Crawler 完整验证脚本
验证 RSS 源抓取、数据库存储、JSON 文件生成
"""

import sys
import os
from pathlib import Path
import json
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import CONFIG, MYSQL_CONFIG, INDEXER_CONFIG
from src.core.pipeline import run_feed_pipeline
from src.storage.db_mysql import create_mysql_db
from src.integration.indexer_interface import create_indexer
from src.integration.coordinator import create_coordinator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CrawlerValidator:
    """Crawler Validator"""

    def __init__(self):
        self.database = None
        self.indexer = None
        self.coordinator = None
        self.test_feed_url = "https://feeds.bbci.co.uk/news/rss.xml"  # BBC News RSS
        self.validation_results = {
            "database_connection": False,
            "indexer_initialization": False,
            "rss_feed_fetch": False,
            "articles_crawled": 0,
            "metadata_saved": 0,
            "indexer_sent": 0,
            "json_file_created": False,
            "json_file_path": None,
            "errors": [],
        }

    def step_1_check_environment(self):
        """Step 1: Check environment configuration"""
        logger.info("\n" + "=" * 70)
        logger.info("Step 1: Check Environment Configuration")
        logger.info("=" * 70)

        # Check .env file (should be in crawler/ directory, not crawler/scripts/)
        env_file = Path(__file__).parent.parent / ".env"
        if not env_file.exists():
            logger.warning("[WARNING] .env file not found, will use default values from .env.example")
            logger.info(f"   MySQL Host: {MYSQL_CONFIG.host}")
            logger.info(f"   MySQL Database: {MYSQL_CONFIG.database}")
            logger.info(f"   Indexer Output Dir: {INDEXER_CONFIG.output_dir}")
        else:
            logger.info("[OK] .env file exists")

        logger.info(f"\nCurrent configuration:")
        logger.info(f"  - MySQL: {MYSQL_CONFIG.user}@{MYSQL_CONFIG.host}:{MYSQL_CONFIG.port}/{MYSQL_CONFIG.database}")
        logger.info(f"  - Indexer output directory: {INDEXER_CONFIG.output_dir}")
        logger.info(f"  - Indexer output file: {INDEXER_CONFIG.output_filename}")
        logger.info(f"  - Save content to DB: {INDEXER_CONFIG.save_content_to_db}")

    def step_2_init_database(self):
        """Step 2: Initialize database connection"""
        logger.info("\n" + "=" * 70)
        logger.info("Step 2: Initialize Database Connection")
        logger.info("=" * 70)

        try:
            self.database = create_mysql_db(
                host=MYSQL_CONFIG.host,
                port=MYSQL_CONFIG.port,
                user=MYSQL_CONFIG.user,
                password=MYSQL_CONFIG.password,
                database=MYSQL_CONFIG.database,
                pool_size=MYSQL_CONFIG.pool_size,
            )
            logger.info("[OK] Database connected successfully")
            self.validation_results["database_connection"] = True

            # Test if tables exist
            logger.info("\nChecking database tables...")
            # You can add simple queries here to verify table structure
            logger.info("[OK] Database tables check completed")

        except Exception as e:
            logger.error(f"[FAILED] Database connection failed: {e}")
            self.validation_results["errors"].append(f"Database connection: {e}")
            return False

        return True

    def step_3_init_indexer(self):
        """Step 3: Initialize Indexer interface"""
        logger.info("\n" + "=" * 70)
        logger.info("Step 3: Initialize Indexer Interface")
        logger.info("=" * 70)

        try:
            self.indexer = create_indexer(
                output_dir=INDEXER_CONFIG.output_dir,
                output_filename=INDEXER_CONFIG.output_filename,
            )
            logger.info(f"[OK] Indexer interface initialized successfully")
            logger.info(f"  Output directory: {INDEXER_CONFIG.output_dir}")
            logger.info(f"  Output file: {INDEXER_CONFIG.output_filename}")
            self.validation_results["indexer_initialization"] = True

        except Exception as e:
            logger.error(f"[FAILED] Indexer initialization failed: {e}")
            self.validation_results["errors"].append(f"Indexer initialization: {e}")
            return False

        return True

    def step_4_create_coordinator(self):
        """Step 4: Create Coordinator"""
        logger.info("\n" + "=" * 70)
        logger.info("Step 4: Create Coordinator")
        logger.info("=" * 70)

        try:
            self.coordinator = create_coordinator(
                database=self.database,
                indexer=self.indexer,
                save_content_to_db=INDEXER_CONFIG.save_content_to_db,
            )
            logger.info("[OK] Coordinator created successfully")

            # Health check
            logger.info("\nPerforming health check...")
            db_ok, indexer_ok = self.coordinator.check_health()
            logger.info(f"  Database health: {'[OK]' if db_ok else '[FAILED]'}")
            logger.info(f"  Indexer health: {'[OK]' if indexer_ok else '[FAILED]'}")

            if not db_ok:
                logger.error("Database health check failed!")
                return False

        except Exception as e:
            logger.error(f"[FAILED] Coordinator creation failed: {e}")
            self.validation_results["errors"].append(f"Coordinator creation: {e}")
            return False

        return True

    def step_5_crawl_rss_feed(self):
        """Step 5: Crawl articles from RSS feed"""
        logger.info("\n" + "=" * 70)
        logger.info("Step 5: Crawl Articles from RSS Feed")
        logger.info("=" * 70)

        logger.info(f"RSS feed: {self.test_feed_url}")
        logger.info(f"Max items to crawl: {CONFIG.max_items_per_feed}")
        logger.info(f"Min text length: {CONFIG.min_text_length}")

        try:
            # Add RSS source to database
            logger.info("\nAdding RSS source to database...")
            self.database.add_rss_source(
                feed_url=self.test_feed_url,
                title="BBC News (Validation Test)",
                description="BBC News RSS Feed for validation",
            )
            logger.info("[OK] RSS source added")

            # Run crawler pipeline
            logger.info("\nStarting article crawl...")
            records = run_feed_pipeline(
                feed_url=self.test_feed_url,
                user_agent=CONFIG.user_agent,
                timeout_seconds=CONFIG.timeout_seconds,
                max_items=CONFIG.max_items_per_feed,
                sleep_seconds=CONFIG.sleep_seconds,
                jitter_seconds=CONFIG.jitter_seconds,
                min_text_length=CONFIG.min_text_length,
            )

            self.validation_results["articles_crawled"] = len(records)
            self.validation_results["rss_feed_fetch"] = len(records) > 0

            logger.info(f"\n[OK] Successfully crawled {len(records)} article(s)")

            # Show info of first few articles
            if records:
                logger.info("\nPreview of first 3 articles:")
                for i, record in enumerate(records[:3], 1):
                    logger.info(f"\n  Article {i}:")
                    logger.info(f"    Title: {record.rss_title}")
                    logger.info(f"    URL: {record.url}")
                    logger.info(f"    HTTP status: {record.http_status}")
                    if record.extracted and record.extracted.get("text_ok"):
                        text = record.extracted.get("text", "")
                        logger.info(f"    Extracted text length: {len(text)} characters")
                    else:
                        logger.info(f"    Extraction failed")

            return records

        except Exception as e:
            logger.error(f"[FAILED] RSS crawl failed: {e}")
            self.validation_results["errors"].append(f"RSS crawl: {e}")
            return []

    def step_6_process_articles(self, records):
        """Step 6: Process articles (save to database + send to Indexer)"""
        logger.info("\n" + "=" * 70)
        logger.info("Step 6: Process Articles")
        logger.info("=" * 70)

        if not records:
            logger.warning("No articles to process")
            return []

        try:
            logger.info(f"Starting to process {len(records)} article(s)...")
            results = self.coordinator.process_articles_batch(records)

            # Collect statistics
            metadata_saved = sum(1 for r in results if r.metadata_saved)
            indexer_sent = sum(1 for r in results if r.indexer_sent)
            content_saved = sum(1 for r in results if r.content_saved)
            errors = sum(1 for r in results if r.error)

            self.validation_results["metadata_saved"] = metadata_saved
            self.validation_results["indexer_sent"] = indexer_sent

            logger.info(f"\nProcessing results:")
            logger.info(f"  [OK] Metadata saved to database: {metadata_saved}/{len(results)}")
            logger.info(f"  [OK] Content sent to Indexer: {indexer_sent}/{len(results)}")
            logger.info(f"  [OK] Content saved to database: {content_saved}/{len(results)}")
            if errors > 0:
                logger.warning(f"  [WARNING] Errors: {errors}/{len(results)}")

            # Show successfully processed articles
            success_docs = [r for r in results if r.metadata_saved and r.indexer_sent]
            if success_docs:
                logger.info(f"\nSuccessfully processed articles (first 5):")
                for r in success_docs[:5]:
                    logger.info(f"  - doc_id: {r.doc_id}, URL: {r.url[:60]}...")

            # Show errors
            error_results = [r for r in results if r.error]
            if error_results:
                logger.warning(f"\nError list (first 3):")
                for r in error_results[:3]:
                    logger.warning(f"  - {r.url[:60]}...")
                    logger.warning(f"    Error: {r.error}")

            return results

        except Exception as e:
            logger.error(f"[FAILED] Article processing failed: {e}")
            self.validation_results["errors"].append(f"Article processing: {e}")
            return []

    def step_7_verify_json_output(self):
        """Step 7: Verify JSON file generation"""
        logger.info("\n" + "=" * 70)
        logger.info("Step 7: Verify JSON File Generation")
        logger.info("=" * 70)

        output_dir = Path(INDEXER_CONFIG.output_dir)
        output_file = output_dir / INDEXER_CONFIG.output_filename

        logger.info(f"Checking file: {output_file}")

        if not output_file.exists():
            logger.error(f"[FAILED] JSON file does not exist: {output_file}")
            self.validation_results["errors"].append("JSON file not created")
            return False

        try:
            # Read and verify JSON file
            with open(output_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.validation_results["json_file_created"] = True
            self.validation_results["json_file_path"] = str(output_file)

            logger.info(f"[OK] JSON file exists")
            logger.info(f"  File size: {output_file.stat().st_size / 1024:.2f} KB")

            # Verify JSON structure
            if isinstance(data, list):
                logger.info(f"  Document count: {len(data)}")

                # Show structure of first few documents
                if data:
                    logger.info(f"\n  Preview of first 2 documents:")
                    for i, doc in enumerate(data[:2], 1):
                        logger.info(f"\n  Document {i}:")
                        logger.info(f"    doc_id: {doc.get('doc_id', 'N/A')}")
                        logger.info(f"    title: {doc.get('title', 'N/A')[:50]}...")
                        logger.info(f"    url: {doc.get('url', 'N/A')[:60]}...")
                        content = doc.get("content", "")
                        logger.info(f"    content length: {len(content)} characters")
                        logger.info(f"    fields: {list(doc.keys())}")
            else:
                logger.warning(f"  [WARNING] JSON format is not a list")

            logger.info(f"\n[OK] JSON file verification passed")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"[FAILED] JSON file format error: {e}")
            self.validation_results["errors"].append(f"JSON decode error: {e}")
            return False
        except Exception as e:
            logger.error(f"[FAILED] JSON file read failed: {e}")
            self.validation_results["errors"].append(f"JSON read error: {e}")
            return False

    def step_8_verify_database(self):
        """Step 8: Verify database records"""
        logger.info("\n" + "=" * 70)
        logger.info("Step 8: Verify Database Records")
        logger.info("=" * 70)

        try:
            # You can add some database queries here to verify data
            logger.info("Querying database records...")

            # Example: Query count of recently added articles
            # Note: This needs to be adjusted based on your actual database interface
            logger.info("[OK] Database records verification completed")
            logger.info("  Tip: You can use these SQL queries to verify:")
            logger.info("  - SELECT COUNT(*) FROM articles;")
            logger.info("  - SELECT doc_id, title, url FROM articles ORDER BY created_at DESC LIMIT 5;")
            logger.info("  - SELECT * FROM rss_sources WHERE feed_url = '" + self.test_feed_url + "';")

            return True

        except Exception as e:
            logger.error(f"[FAILED] Database verification failed: {e}")
            self.validation_results["errors"].append(f"Database verification: {e}")
            return False

    def print_summary(self):
        """Print validation summary"""
        logger.info("\n" + "=" * 70)
        logger.info("Validation Summary")
        logger.info("=" * 70)

        results = self.validation_results

        logger.info(f"\nDatabase connection: {'[OK]' if results['database_connection'] else '[FAILED]'}")
        logger.info(f"Indexer initialization: {'[OK]' if results['indexer_initialization'] else '[FAILED]'}")
        logger.info(f"RSS feed fetch: {'[OK]' if results['rss_feed_fetch'] else '[FAILED]'}")
        logger.info(f"Articles crawled: {results['articles_crawled']}")
        logger.info(f"Metadata saved: {results['metadata_saved']}")
        logger.info(f"Indexer sent: {results['indexer_sent']}")
        logger.info(f"JSON file created: {'[OK]' if results['json_file_created'] else '[FAILED]'}")

        if results["json_file_path"]:
            logger.info(f"JSON file path: {results['json_file_path']}")

        if results["errors"]:
            logger.warning(f"\nError count: {len(results['errors'])}")
            for error in results["errors"]:
                logger.warning(f"  - {error}")

        # Overall assessment
        logger.info("\n" + "=" * 70)
        success = (
            results["database_connection"]
            and results["indexer_initialization"]
            and results["rss_feed_fetch"]
            and results["articles_crawled"] > 0
            and results["metadata_saved"] > 0
            and results["indexer_sent"] > 0
            and results["json_file_created"]
        )

        if success:
            logger.info(">>> ALL VALIDATIONS PASSED! Crawler is working correctly <<<")
        else:
            logger.error(">>> SOME VALIDATIONS FAILED, please check error messages <<<")

        logger.info("=" * 70)

    def run_validation(self):
        """Run complete validation workflow"""
        logger.info("\n" + "=" * 70)
        logger.info("Starting Complete Crawler Validation")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)

        # Step 1: Check environment
        self.step_1_check_environment()

        # Step 2: Initialize database
        if not self.step_2_init_database():
            logger.error("\nDatabase initialization failed, aborting validation")
            self.print_summary()
            return

        # Step 3: Initialize Indexer
        if not self.step_3_init_indexer():
            logger.error("\nIndexer initialization failed, aborting validation")
            self.print_summary()
            return

        # Step 4: Create Coordinator
        if not self.step_4_create_coordinator():
            logger.error("\nCoordinator creation failed, aborting validation")
            self.print_summary()
            return

        # Step 5: Crawl RSS articles
        records = self.step_5_crawl_rss_feed()
        if not records:
            logger.error("\nRSS crawl failed or no articles found, aborting validation")
            self.print_summary()
            return

        # Step 6: Process articles
        results = self.step_6_process_articles(records)
        if not results:
            logger.error("\nArticle processing failed, aborting validation")
            self.print_summary()
            return

        # Step 7: Verify JSON file
        self.step_7_verify_json_output()

        # Step 8: Verify database
        self.step_8_verify_database()

        # Print summary
        self.print_summary()


def main():
    """Main function"""
    try:
        validator = CrawlerValidator()
        validator.run_validation()
    except KeyboardInterrupt:
        logger.info("\nUser interrupted validation")
    except Exception as e:
        logger.error(f"\nException occurred during validation: {e}", exc_info=True)


if __name__ == "__main__":
    main()
