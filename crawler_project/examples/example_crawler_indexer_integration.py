"""
Full Integration Example: Crawler → Database → Indexer
Demonstrates how to pass crawled articles to the Indexer team's indexer
"""

from config import CONFIG, MYSQL_CONFIG, INDEXER_CONFIG
from crawler.pipeline import run_feed_pipeline
from crawler.db_mysql import create_mysql_db
from crawler.indexer_interface import create_indexer
from crawler.coordinator import create_coordinator
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Full Integration Example"""

    logger.info("=" * 70)
    logger.info("Crawler → Indexer Integration Example")
    logger.info("=" * 70)

    # ============================================================
    # Step 1: Initialize Database
    # ============================================================
    logger.info("\n[Step 1] Initializing MySQL database...")
    try:
        database = create_mysql_db(
            host=MYSQL_CONFIG.host,
            port=MYSQL_CONFIG.port,
            user=MYSQL_CONFIG.user,
            password=MYSQL_CONFIG.password,
            database=MYSQL_CONFIG.database,
            pool_size=MYSQL_CONFIG.pool_size,
        )
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return

    # ============================================================
    # Step 2: Initialize Indexer interface
    # ============================================================
    logger.info(f"\n[Step 2] Initializing Indexer interface...")
    logger.info(f"   Output: {INDEXER_CONFIG.output_dir}/{INDEXER_CONFIG.output_filename}")

    try:
        indexer = create_indexer(
            output_dir=INDEXER_CONFIG.output_dir,
            output_filename=INDEXER_CONFIG.output_filename,
        )
        logger.info("Indexer interface initialized")
    except Exception as e:
        logger.error(f"Failed to initialize indexer: {e}")
        return

    # ============================================================
    # Step 3: Create coordinator
    # ============================================================
    logger.info(f"\n[Step 3] Creating coordinator...")
    coordinator = create_coordinator(
        database=database,
        indexer=indexer,
        save_content_to_db=INDEXER_CONFIG.save_content_to_db,
    )
    logger.info("Coordinator created")

    # ============================================================
    # Step 4: Health check
    # ============================================================
    logger.info("\n[Step 4] Health check...")
    db_ok, indexer_ok = coordinator.check_health()
    logger.info(f"   Database: {'OK' if db_ok else 'FAILED'}")
    logger.info(f"   Indexer:  {'OK' if indexer_ok else 'FAILED'}")

    if not db_ok:
        logger.error("Database not available, aborting")
        return

    # ============================================================
    # Step 5: Configure RSS source
    # ============================================================
    feed_url = "https://feeds.bbci.co.uk/news/rss.xml"
    logger.info(f"\n[Step 5] Adding RSS source...")
    logger.info(f"   Feed: {feed_url}")

    database.add_rss_source(feed_url=feed_url, title="BBC News", description="BBC News RSS Feed")
    logger.info("RSS source added")

    # ============================================================
    # Step 6: Run crawler pipeline
    # ============================================================
    logger.info(f"\n[Step 6] Running crawler pipeline...")
    logger.info(f"   Max items: {CONFIG.max_items_per_feed}")

    records = run_feed_pipeline(
        feed_url=feed_url,
        user_agent=CONFIG.user_agent,
        timeout_seconds=CONFIG.timeout_seconds,
        max_items=CONFIG.max_items_per_feed,
        sleep_seconds=CONFIG.sleep_seconds,
        jitter_seconds=CONFIG.jitter_seconds,
        min_text_length=CONFIG.min_text_length,
    )
    logger.info(f"Crawled {len(records)} articles")

    # ============================================================
    # Step 7: Process articles (save metadata + send to Indexer)
    # ============================================================
    logger.info(f"\n[Step 7] Processing articles...")
    logger.info("   - Saving metadata to database")
    logger.info("   - Converting to indexer format")
    logger.info("   - Accumulating for batch write")

    results = coordinator.process_articles_batch(records)
    logger.info("Articles processed")

    # ============================================================
    # Step 8: Statistics and reporting
    # ============================================================
    logger.info("\n" + "=" * 70)
    logger.info("RESULTS SUMMARY")
    logger.info("=" * 70)

    total = len(results)
    metadata_saved = sum(1 for r in results if r.metadata_saved)
    indexer_sent = sum(1 for r in results if r.indexer_sent)
    errors = sum(1 for r in results if r.error)

    logger.info(f"Total articles:           {total}")
    logger.info(f"Metadata saved to DB:     {metadata_saved}")
    logger.info(f"Sent to indexer:          {indexer_sent}")
    logger.info(f"Errors:                   {errors}")

    # Display generated file
    output_file = Path(INDEXER_CONFIG.output_dir) / INDEXER_CONFIG.output_filename
    if output_file.exists():
        file_size = output_file.stat().st_size
        logger.info(f"\nIndexer input file generated:")
        logger.info(f"   Path: {output_file}")
        logger.info(f"   Size: {file_size:,} bytes")
        logger.info(f"\nNext step: Run the indexer to build the inverted index")
        logger.info(f"   cd {Path(INDEXER_CONFIG.output_dir).parent}")
        logger.info(f"   python indexer.py")
    else:
        logger.warning(f"Output file not found: {output_file}")

    # Display successfully processed articles
    success_docs = [r for r in results if r.metadata_saved and r.indexer_sent]
    if success_docs:
        logger.info(f"\nSuccessfully processed articles (showing first 5):")
        for i, r in enumerate(success_docs[:5], 1):
            logger.info(f"   {i}. doc_id={r.doc_id}: {r.url[:60]}...")

    # Display error examples
    error_results = [r for r in results if r.error]
    if error_results:
        logger.info(f"\nErrors encountered (showing first 3):")
        for i, r in enumerate(error_results[:3], 1):
            logger.info(f"   {i}. {r.url[:50]}...")
            logger.info(f"      Error: {r.error}")

    logger.info("\n" + "=" * 70)
    logger.info("Integration example completed!")
    logger.info("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user")
    except Exception as e:
        logger.error(f"\nError: {e}")
        import traceback

        traceback.print_exc()
