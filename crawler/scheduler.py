"""
Crawler Scheduled Task Scheduler
Implements periodic RSS feed article fetching using APScheduler
"""

import sys
import os
import logging
import signal
from pathlib import Path
from datetime import datetime
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from src.config import CONFIG, MYSQL_CONFIG, INDEXER_CONFIG
from src.core.pipeline import run_feed_pipeline
from src.storage.db_mysql import create_mysql_db
from src.integration.indexer_interface import create_indexer
from src.integration.coordinator import create_coordinator

# Configure logging
log_dir = os.getenv("LOG_DIR", "/logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "crawler_scheduler.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class CrawlerScheduler:
    """Crawler scheduled task scheduler"""

    def __init__(self):
        self.scheduler = BlockingScheduler(timezone="UTC")
        self.database = None
        self.indexer = None
        self.coordinator = None
        self.feeds = []
        self.stats = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "total_articles": 0,
        }

    def initialize_components(self):
        """Initialise database, indexer, and coordinator"""
        try:
            logger.info("Initializing components...")

            # Initialise database
            self.database = create_mysql_db(
                host=MYSQL_CONFIG.host,
                port=MYSQL_CONFIG.port,
                user=MYSQL_CONFIG.user,
                password=MYSQL_CONFIG.password,
                database=MYSQL_CONFIG.database,
                pool_size=MYSQL_CONFIG.pool_size,
            )
            logger.info("Database initialized")

            # Initialise indexer
            self.indexer = create_indexer(
                output_dir=INDEXER_CONFIG.output_dir,
                output_filename=INDEXER_CONFIG.output_filename,
                dedup_threshold_mb=INDEXER_CONFIG.dedup_threshold_mb,
            )
            logger.info("Indexer initialized")

            # Initialise coordinator
            self.coordinator = create_coordinator(
                database=self.database,
                indexer=self.indexer,
                save_content_to_db=INDEXER_CONFIG.save_content_to_db,
            )
            logger.info("Coordinator initialized")

            # Health check
            db_ok, indexer_ok = self.coordinator.check_health()
            if not db_ok or not indexer_ok:
                raise Exception("Component health check failed")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            return False

    def load_feeds(self):
        """Load RSS feed configuration from feeds.yaml"""
        try:
            feeds_file = Path(__file__).parent / "sources" / "feeds.yaml"
            with open(feeds_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                self.feeds = config.get("feeds", [])

            logger.info(f"Loaded {len(self.feeds)} RSS feeds from configuration")
            for feed in self.feeds:
                logger.info(f"  - {feed['name']}: {feed['url']}")

            return True

        except Exception as e:
            logger.error(f"Failed to load feeds configuration: {e}")
            return False

    def crawl_all_feeds(self):
        """
        Scheduled task: Crawl all RSS feeds
        Executed every hour
        """
        job_start = datetime.now()
        logger.info("=" * 70)
        logger.info(f"Starting scheduled crawl job at {job_start}")
        logger.info("=" * 70)

        self.stats["total_runs"] += 1
        total_articles = 0
        successful_feeds = 0
        failed_feeds = 0

        try:
            for feed in self.feeds:
                feed_url = feed["url"]
                feed_name = feed["name"]

                try:
                    logger.info(f"\nCrawling feed: {feed_name}")
                    logger.info(f"URL: {feed_url}")

                    # Add RSS source to database
                    self.database.add_rss_source(
                        feed_url=feed_url, title=feed_name, description=f"Auto-crawled from scheduler"
                    )

                    # Run crawler pipeline
                    articles = run_feed_pipeline(
                        feed_url=feed_url,
                        user_agent=CONFIG.user_agent,
                        timeout_seconds=CONFIG.timeout_seconds,
                        max_items=CONFIG.max_items_per_feed,
                        sleep_seconds=CONFIG.sleep_seconds,
                        jitter_seconds=CONFIG.jitter_seconds,
                        min_text_length=CONFIG.min_text_length,
                    )

                    # Process articles (save to database and indexer)
                    if articles:
                        results = self.coordinator.process_articles_batch(articles)

                        # Statistics
                        metadata_saved = sum(1 for r in results if r.metadata_saved)
                        indexer_sent = sum(1 for r in results if r.indexer_sent)

                        logger.info(
                            f"{feed_name}: {len(articles)} crawled, {metadata_saved} saved, {indexer_sent} indexed"
                        )

                        total_articles += len(articles)
                        successful_feeds += 1
                    else:
                        logger.warning(f"{feed_name}: No articles found")
                        successful_feeds += 1

                except Exception as e:
                    logger.error(f"Failed to crawl {feed_name}: {e}")
                    failed_feeds += 1
                    continue

            # Job completed
            job_end = datetime.now()
            duration = (job_end - job_start).total_seconds()

            self.stats["successful_runs"] += 1
            self.stats["total_articles"] += total_articles

            logger.info("\n" + "=" * 70)
            logger.info("Crawl job completed successfully")
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info(f"Feeds: {successful_feeds} successful, {failed_feeds} failed")
            logger.info(f"Total articles: {total_articles}")
            logger.info("=" * 70)

        except Exception as e:
            self.stats["failed_runs"] += 1
            logger.error(f"Crawl job failed: {e}", exc_info=True)

    def verify_json_integrity(self):
        """
        Scheduled task: Verify JSON file integrity
        Executed daily at 3:00 AM
        """
        logger.info("=" * 70)
        logger.info(f"Running JSON integrity check at {datetime.now()}")
        logger.info("=" * 70)

        try:
            from scripts.check_json_duplicates import check_duplicates

            if not check_duplicates():
                logger.warning("JSON file contains duplicate IDs!")
                # Optional: Auto-fix or send alert
            else:
                logger.info("JSON file integrity check passed")

            # Get file statistics
            stats = self.indexer.get_file_stats()
            logger.info(f"JSON file stats: {stats}")

        except Exception as e:
            logger.error(f"JSON integrity check failed: {e}")

    def print_scheduler_stats(self):
        """
        Scheduled task: Print scheduler statistics
        Executed daily at 0:00 AM
        """
        logger.info("=" * 70)
        logger.info("Scheduler Statistics")
        logger.info("=" * 70)
        logger.info(f"Total runs: {self.stats['total_runs']}")
        logger.info(f"Successful runs: {self.stats['successful_runs']}")
        logger.info(f"Failed runs: {self.stats['failed_runs']}")
        logger.info(f"Total articles crawled: {self.stats['total_articles']}")
        if self.stats["total_runs"] > 0:
            success_rate = (self.stats["successful_runs"] / self.stats["total_runs"]) * 100
            logger.info(f"Success rate: {success_rate:.2f}%")
        logger.info("=" * 70)

    def job_listener(self, event):
        """Job execution listener"""
        if event.exception:
            logger.error(f"Job {event.job_id} failed with exception: {event.exception}")
        else:
            logger.debug(f"Job {event.job_id} executed successfully")

    def setup_jobs(self):
        """Configure all scheduled tasks"""
        # Task 1: Crawl RSS feeds every hour
        self.scheduler.add_job(
            self.crawl_all_feeds,
            trigger=IntervalTrigger(hours=1),
            id="crawl_feeds",
            name="Crawl RSS Feeds",
            replace_existing=True,
            max_instances=1,  # Only run one instance at a time
            misfire_grace_time=300,  # Grace time for missed jobs (seconds)
        )
        logger.info("Job 'crawl_feeds' scheduled: every hour")

        # Task 2: Verify JSON integrity daily at 3:00 AM
        self.scheduler.add_job(
            self.verify_json_integrity,
            trigger=CronTrigger(hour=3, minute=0),
            id="verify_json",
            name="Verify JSON Integrity",
            replace_existing=True,
        )
        logger.info("Job 'verify_json' scheduled: daily at 3:00 AM")

        # Task 3: Print statistics daily at 0:00 AM
        self.scheduler.add_job(
            self.print_scheduler_stats,
            trigger=CronTrigger(hour=0, minute=0),
            id="print_stats",
            name="Print Statistics",
            replace_existing=True,
        )
        logger.info("Job 'print_stats' scheduled: daily at 0:00 AM")

        # Add event listener
        self.scheduler.add_listener(self.job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    def start(self):
        """Start the scheduler"""
        logger.info("\n" + "=" * 70)
        logger.info("Crawler Scheduler Starting")
        logger.info("=" * 70)

        # Initialise components
        if not self.initialize_components():
            logger.error("Failed to initialize components, exiting")
            return False

        # Load RSS feed configuration
        if not self.load_feeds():
            logger.error("Failed to load feeds configuration, exiting")
            return False

        # Configure scheduled tasks
        self.setup_jobs()

        # Optional: Execute once immediately on startup
        logger.info("\n>>> Running initial crawl before starting schedule...")
        try:
            self.crawl_all_feeds()
            logger.info(">>> Initial crawl completed successfully")
        except Exception as e:
            logger.error(f"Initial crawl failed: {e}", exc_info=True)
            logger.warning("Scheduler will continue despite initial crawl failure")

        # Print scheduled jobs info
        logger.info("\n" + "=" * 70)
        logger.info("Configured Jobs:")
        logger.info("=" * 70)
        logger.info("  - Crawl RSS Feeds: every 1 hour")
        logger.info("  - Verify JSON Integrity: daily at 3:00 AM UTC")
        logger.info("  - Print Statistics: daily at 0:00 AM UTC")

        logger.info("\n" + "=" * 70)
        logger.info("Scheduler is running... Press Ctrl+C to stop")
        logger.info("=" * 70)

        # Start scheduler (blocking)
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("\nShutting down scheduler...")
            self.shutdown()

    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down scheduler gracefully...")
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")


def main():
    """Main function"""
    scheduler = CrawlerScheduler()

    # Register signal handlers (graceful exit)
    def signal_handler(sig, frame):
        logger.info("\nReceived interrupt signal")
        scheduler.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start scheduler
    scheduler.start()


if __name__ == "__main__":
    main()
