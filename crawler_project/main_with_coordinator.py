"""
Integrated version of main.py
Use coordinator to save crawled article metadata to database and send content to indexer
"""

from config import CONFIG, MYSQL_CONFIG, INDEXER_CONFIG
from crawler.pipeline import run_feed_pipeline
from crawler.db_mysql import create_mysql_db
from crawler.indexer_interface import create_indexer
from crawler.coordinator import create_coordinator
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main function: Integrate Crawler, Database, and Indexer"""

    # Configure RSS source
    feed_url = "https://feeds.bbci.co.uk/news/rss.xml"

    # More RSS source examples
    # feeds = [
    #     "https://feeds.bbci.co.uk/news/rss.xml",
    #     "https://www.theguardian.com/world/rss",
    #     "https://www.ft.com/rss/home",
    # ]

    logger.info("=" * 60)
    logger.info("Starting Web Searcher Crawler")
    logger.info("=" * 60)

    # Step 1: Initialize Database
    logger.info("Initializing MySQL database...")
    try:
        database = create_mysql_db(
            host=MYSQL_CONFIG.host,
            port=MYSQL_CONFIG.port,
            user=MYSQL_CONFIG.user,
            password=MYSQL_CONFIG.password,
            database=MYSQL_CONFIG.database,
            pool_size=MYSQL_CONFIG.pool_size,
        )
        logger.info("✓ Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return

    # Step 2: Initialize Indexer interface
    logger.info("Initializing Indexer interface...")
    try:
        indexer = create_indexer(
            output_dir=INDEXER_CONFIG.output_dir,
            output_filename=INDEXER_CONFIG.output_filename,
        )
        logger.info("✓ Indexer interface initialized")
    except Exception as e:
        logger.error(f"Failed to initialize indexer: {e}")
        return

    # Step 3: Create coordinator
    logger.info("Creating coordinator...")
    coordinator = create_coordinator(
        database=database,
        indexer=indexer,
        save_content_to_db=INDEXER_CONFIG.save_content_to_db,
    )
    logger.info("✓ Coordinator created")

    # Step 4: Health check
    logger.info("Performing health check...")
    db_ok, indexer_ok = coordinator.check_health()
    if not db_ok:
        logger.error("Database health check failed! Aborting.")
        return
    if not indexer_ok:
        logger.warning("Indexer health check failed! Will continue but indexing may fail.")

    # Step 5: Add RSS source to database
    logger.info(f"Adding RSS source: {feed_url}")
    database.add_rss_source(feed_url=feed_url, title="BBC News", description="BBC News RSS Feed")

    # Step 6: Run crawler pipeline
    logger.info(f"Running crawler pipeline for: {feed_url}")
    logger.info("-" * 60)
    records = run_feed_pipeline(
        feed_url=feed_url,
        user_agent=CONFIG.user_agent,
        timeout_seconds=CONFIG.timeout_seconds,
        max_items=CONFIG.max_items_per_feed,
        sleep_seconds=CONFIG.sleep_seconds,
        jitter_seconds=CONFIG.jitter_seconds,
        min_text_length=CONFIG.min_text_length,
    )
    logger.info(f"✓ Crawled {len(records)} articles")

    # Step 7: Process all articles using coordinator
    logger.info("-" * 60)
    logger.info("Processing articles (saving metadata + sending to indexer)...")
    results = coordinator.process_articles_batch(records)

    # Step 8: Summarize results
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    total = len(results)
    metadata_saved = sum(1 for r in results if r.metadata_saved)
    indexer_sent = sum(1 for r in results if r.indexer_sent)
    content_saved = sum(1 for r in results if r.content_saved)
    errors = sum(1 for r in results if r.error)

    logger.info(f"Total articles processed:     {total}")
    logger.info(f"Metadata saved to DB:         {metadata_saved}")
    logger.info(f"Content sent to indexer:      {indexer_sent}")
    logger.info(f"Content saved to DB:          {content_saved}")
    logger.info(f"Errors:                       {errors}")

    # Print successfully processed article doc_ids
    success_docs = [r for r in results if r.metadata_saved and r.indexer_sent]
    if success_docs:
        logger.info("\nSuccessfully processed articles (doc_id):")
        for r in success_docs[:10]:  # Only show the first 10
            logger.info(f"  - doc_id: {r.doc_id}, url: {r.url}")
        if len(success_docs) > 10:
            logger.info(f"  ... and {len(success_docs) - 10} more")

    # Print errors
    error_results = [r for r in results if r.error]
    if error_results:
        logger.warning("\nErrors encountered:")
        for r in error_results[:5]:  # Only show the first 5 errors
            logger.warning(f"  - {r.url}: {r.error}")
        if len(error_results) > 5:
            logger.warning(f"  ... and {len(error_results) - 5} more errors")

    logger.info("=" * 60)
    logger.info("Crawler completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
