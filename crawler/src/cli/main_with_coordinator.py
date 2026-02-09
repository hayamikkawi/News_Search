"""
Integrated version of main.py
Use coordinator to save crawled article metadata to database and send content to indexer
"""

from ..config import CONFIG, MYSQL_CONFIG, INDEXER_CONFIG
from ..core.pipeline import run_feed_pipeline
from ..storage.db_mysql import create_mysql_db
from ..integration.indexer_interface import create_indexer
from ..integration.coordinator import create_coordinator
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

    # Step 7: Process articles through coordinator
    logger.info("Processing articles through coordinator...")
    logger.info("-" * 60)
    results = coordinator.process_articles_batch(records)

    # Step 8: Statistics
    logger.info("=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)

    total = len(results)
    metadata_saved = sum(1 for r in results if r.metadata_saved)
    indexer_sent = sum(1 for r in results if r.indexer_sent)
    content_saved = sum(1 for r in results if r.content_saved)
    failed = total - metadata_saved

    logger.info(f"Total articles: {total}")
    logger.info(f"Metadata saved to database: {metadata_saved}")
    logger.info(f"Content sent to indexer: {indexer_sent}")
    logger.info(f"Content saved to database: {content_saved}")
    logger.info(f"Failed: {failed}")

    if failed > 0:
        logger.warning("Failed articles:")
        for r in results:
            if not r.metadata_saved:
                logger.warning(f"  - {r.url}: {r.error}")

    logger.info("=" * 60)
    logger.info("Crawler completed successfully")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
