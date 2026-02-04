"""
Test Example: Demonstrate Coordinator Workflow
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from crawler.db_mysql import create_mysql_db
from crawler.indexer_interface import create_indexer
from crawler.coordinator import create_coordinator
from crawler.models import ArticleRecord
from config import MYSQL_CONFIG
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_coordinator_workflow():
    """Test complete Coordinator workflow"""

    logger.info("=" * 60)
    logger.info("Testing Coordinator Workflow")
    logger.info("=" * 60)

    # 1. Create database instance
    logger.info("\n1. Creating database instance...")
    db = create_mysql_db(
        host=MYSQL_CONFIG.host,
        port=MYSQL_CONFIG.port,
        user=MYSQL_CONFIG.user,
        password=MYSQL_CONFIG.password,
        database=MYSQL_CONFIG.database,
    )
    logger.info("Database created")

    # 2. Create indexer interface (dummy type for testing)
    logger.info("\n2. Creating indexer interface (dummy type for testing)...")
    indexer = create_indexer("dummy")
    logger.info("Indexer interface created")

    # 3. Create coordinator
    logger.info("\n3. Creating coordinator...")
    coordinator = create_coordinator(
        database=db,
        indexer=indexer,
        save_content_to_db=False,  # Do not save content to DB
    )
    logger.info("Coordinator created")

    # 4. Health check
    logger.info("\n4. Health check...")
    db_ok, indexer_ok = coordinator.check_health()
    logger.info(f"Database: {'OK' if db_ok else 'FAILED'}")
    logger.info(f"Indexer: {'OK' if indexer_ok else 'FAILED'}")

    # 5. Creating test articles
    logger.info("\n5. Creating test articles...")
    test_articles = [
        ArticleRecord(
            url=f"https://example.com/article/{i}",
            final_url=f"https://example.com/article/{i}",
            feed_url="https://example.com/rss",
            rss_title=f"Test Article {i}",
            rss_published_at=datetime.now().isoformat(),
            fetched_at=datetime.now().isoformat(),
            http_status=200,
            error=None,
            extracted={
                "text_ok": True,
                "title": f"Test Article Title {i}",
                "author": "Test Author",
                "date": "2026-02-04",
                "language": "en",
                "text": f"This is the content of test article {i}. " * 50,
            },
        )
        for i in range(1, 4)
    ]
    logger.info(f"Created {len(test_articles)} test articles")

    # 6. Processing articles through coordinator
    logger.info("\n6. Processing articles through coordinator...")
    results = coordinator.process_articles_batch(test_articles)

    # 7. Display results
    logger.info("\n7. Results:")
    logger.info("-" * 60)
    for result in results:
        logger.info(f"URL: {result.url}")
        logger.info(f"  doc_id: {result.doc_id}")
        logger.info(f"  Metadata saved: {result.metadata_saved}")
        logger.info(f"  Indexer sent: {result.indexer_sent}")
        logger.info(f"  Content saved: {result.content_saved}")
        if result.error:
            logger.info(f"  Error: {result.error}")
        logger.info("")

    # 8. Verifying database records
    logger.info("\n8. Verifying database records...")
    for result in results:
        if result.doc_id:
            article = db.get_article_by_id(result.doc_id)
            if article:
                logger.info(f"Found article in DB with doc_id={result.doc_id}")
                logger.info(f"  Title: {article['title']}")
                logger.info(f"  URL: {article['url']}")
                logger.info(f"  Has content: {article['text_content'] is not None}")
            else:
                logger.warning(f"Article with doc_id={result.doc_id} not found in DB")

    logger.info("\n" + "=" * 60)
    logger.info("Test completed!")
    logger.info("=" * 60)


def test_file_based_indexer():
    """Test file-based Indexer"""

    logger.info("\n" + "=" * 60)
    logger.info("Testing File-Based Indexer")
    logger.info("=" * 60)

    # Create file-based indexer
    indexer = create_indexer("file", output_dir="./test_indexer_output")

    # Test sending document
    doc_id = 999
    content = "This is a test document content."
    metadata = {"title": "Test", "author": "Tester"}

    logger.info(f"\nSending document {doc_id} to file-based indexer...")
    success = indexer.send_document(doc_id, content, metadata)

    if success:
        logger.info("Document sent successfully")
        logger.info(f"Check file: ./test_indexer_output/doc_{doc_id}.json")
    else:
        logger.error("Failed to send document")


if __name__ == "__main__":
    try:
        # Test 1: Complete workflow
        test_coordinator_workflow()

        # Test 2: File-based indexer
        test_file_based_indexer()

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
