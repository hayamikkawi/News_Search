"""
MySQL Output Module
Saves crawled articles to a MySQL database
Serves as a MySQL version alternative to output.py
"""

import logging
from typing import List
from .models import ArticleRecord
from .db_mysql import MySQLDatabase

logger = logging.getLogger(__name__)


class MySQLWriter:
    """MySQL Data Writer"""

    def __init__(self, db: MySQLDatabase):
        """
        Initialize MySQL writer
        Args:
            db: MySQLDatabase instance
        """
        self.db = db

    def write_article(self, article: ArticleRecord) -> bool:
        """
        Write a single article

        Args:
            article: Article record

        Returns:
            Whether successful
        """
        try:
            success = self.db.save_article(article)

            # Also log fetch information
            if article.http_status:
                self.db.log_fetch(
                    url=article.url,
                    feed_url=article.feed_url,
                    success=article.http_status == 200 and article.error is None,
                    http_status=article.http_status,
                    error_message=article.error,
                )

            return success
        except Exception as e:
            logger.error(f"Failed to write article to MySQL: {e}")
            return False

    def write_articles(self, articles: List[ArticleRecord]) -> int:
        """
        Batch write articles

        Args:
            articles: List of article records

        Returns:
            Number of successfully written articles
        """
        success_count = 0
        for article in articles:
            if self.write_article(article):
                success_count += 1

        logger.info(f"Batch write completed: {success_count}/{len(articles)} articles successfully written")
        return success_count


def create_mysql_writer(db: MySQLDatabase) -> MySQLWriter:
    """
    Create MySQL writer instance

    Args:
        db: MySQLDatabase instance

    Returns:
        MySQLWriter instance
    """
    return MySQLWriter(db)
