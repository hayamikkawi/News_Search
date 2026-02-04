"""
Coordinator module
Coordinates data flow between Crawler, Database, and Indexer
Implements: 1. Store metadata to database to get doc_id
            2. Pass doc_id and content to indexer
            3. Optional: Save content back to database
"""

import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from ..core.models import ArticleRecord
from ..storage.db_mysql import MySQLDatabase
from .indexer_interface import FileBasedIndexer

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Process result"""

    doc_id: Optional[int]
    url: str
    metadata_saved: bool
    indexer_sent: bool
    content_saved: bool
    error: Optional[str] = None


class CrawlerCoordinator:
    """
    Crawler Coordinator
    Responsible for coordinating the flow of crawler data between Database and Indexer
    """

    def __init__(
        self,
        database: MySQLDatabase,
        indexer: FileBasedIndexer,
        save_content_to_db: bool = False,
    ):
        """
        Initialize the coordinator

        Args:
            database: MySQL Database instance
            indexer: FileBasedIndexer instance
            save_content_to_db: Whether to save content back to the database (default False to save storage space)
        """
        self.database = database
        self.indexer = indexer
        self.save_content_to_db = save_content_to_db

    def process_article(self, article: ArticleRecord) -> ProcessResult:
        """
        Process a single article: store metadata to database, send content to indexer

        Args:
            article: Article record

        Returns:
            ProcessResult: Process result

        Workflow:
        1. Check if the article was successfully extracted
        2. Save metadata to the database and get doc_id
        3. Send doc_id and content to the indexer
        4. (Optional) Save content back to the database
        """
        # Initialize result
        result = ProcessResult(
            doc_id=None,
            url=article.url,
            metadata_saved=False,
            indexer_sent=False,
            content_saved=False,
        )

        # Check if the article was successfully extracted
        extracted = article.extracted or {}
        if not extracted.get("text_ok") or not extracted.get("text"):
            result.error = "Article text extraction failed or text is empty"
            logger.warning(f"Skipping article {article.url}: {result.error}")
            return result

        text_content = extracted.get("text", "")

        # Step 1: Save metadata to the database and get doc_id
        try:
            doc_id = self.database.save_article_metadata_only(article)
            if doc_id is None:
                result.error = "Failed to save metadata to database"
                logger.error(f"Failed to save metadata for {article.url}")
                return result

            result.doc_id = doc_id
            result.metadata_saved = True
            logger.info(f"Metadata saved for {article.url}, doc_id: {doc_id}")
        except Exception as e:
            result.error = f"Database error: {e}"
            logger.error(f"Database error for {article.url}: {e}")
            return result

        # Step 2: Send doc_id and content to indexer
        try:
            metadata_for_indexer = {
                "title": extracted.get("title"),
                "author": extracted.get("author"),
                "date": extracted.get("date"),
                "language": extracted.get("language"),
                "description": extracted.get("description"),
                "url": article.url,
                "feed_url": article.feed_url,
            }

            success = self.indexer.send_document(doc_id=doc_id, content=text_content, metadata=metadata_for_indexer)

            if success:
                result.indexer_sent = True
                logger.info(f"Content sent to indexer for doc_id: {doc_id}")
            else:
                result.error = "Failed to send content to indexer"
                logger.error(f"Failed to send content to indexer for doc_id: {doc_id}")
                # Continue even if indexer fails, metadata has been saved
        except Exception as e:
            result.error = f"Indexer error: {e}"
            logger.error(f"Indexer error for doc_id {doc_id}: {e}")

        # Step 3: (Optional) Save content back to the database
        if self.save_content_to_db:
            try:
                success = self.database.update_article_content(doc_id, text_content)
                if success:
                    result.content_saved = True
                    logger.info(f"Content saved to database for doc_id: {doc_id}")
                else:
                    logger.warning(f"Failed to save content to database for doc_id: {doc_id}")
            except Exception as e:
                logger.error(f"Error saving content to database for doc_id {doc_id}: {e}")

        return result

    def process_articles_batch(self, articles: List[ArticleRecord]) -> List[ProcessResult]:
        """
        Process a batch of articles

        Args:
            articles: List of article records
        Returns:
            List of process results
        """
        results = []
        for article in articles:
            result = self.process_article(article)
            results.append(result)

        # Flush documents to file if using FileBasedIndexer
        try:
            if hasattr(self.indexer, "flush"):
                self.indexer.flush()
                logger.info("Flushed documents to indexer output file")
        except Exception as e:
            logger.error(f"Error flushing documents: {e}")

        # Statistics
        total = len(results)
        metadata_saved = sum(1 for r in results if r.metadata_saved)
        indexer_sent = sum(1 for r in results if r.indexer_sent)
        content_saved = sum(1 for r in results if r.content_saved)

        logger.info(
            f"Batch processing completed: {total} articles, "
            f"{metadata_saved} metadata saved, "
            f"{indexer_sent} sent to indexer, "
            f"{content_saved} content saved to DB"
        )

        return results

    def check_health(self) -> Tuple[bool, bool]:
        """
        Health check

        Returns:
            (database_ok, indexer_ok)
        """
        db_ok = False
        indexer_ok = False

        try:
            # Check database connection
            with self.database.get_connection() as conn:
                if conn and conn.is_connected():
                    db_ok = True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")

        try:
            # Check indexer availability
            indexer_ok = self.indexer.is_available()
        except Exception as e:
            logger.error(f"Indexer health check failed: {e}")

        logger.info(f"Health check: Database={'OK' if db_ok else 'FAILED'}, Indexer={'OK' if indexer_ok else 'FAILED'}")
        return db_ok, indexer_ok


def create_coordinator(
    database: MySQLDatabase,
    indexer: FileBasedIndexer,
    save_content_to_db: bool = False,
) -> CrawlerCoordinator:
    """
    Create a coordinator instance

    Args:
        database: MySQL database instance
        indexer: FileBasedIndexer instance
        save_content_to_db: Whether to save content back to the database

    Returns:
        CrawlerCoordinator instance
    """
    return CrawlerCoordinator(database, indexer, save_content_to_db)
