"""
MySQL database interaction module
Provides functionality for storing and retrieving article data
"""

from mysql.connector import Error, pooling
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import logging
from datetime import datetime

from .models import ArticleRecord

logger = logging.getLogger(__name__)


class MySQLDatabase:
    """MySQL Database Management Class"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        pool_size: int = 5,
    ):
        """
        Initialize MySQL connection pool

        Args:
            host: Database host address
            port: Database port
            user: Username
            password: Password
            database: Database name
            pool_size: Connection pool size
        """
        self.config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": "utf8mb4",
            "autocommit": False,
        }
        self.pool_size = pool_size
        self.pool = None

    def initialize_pool(self):
        """Initialize connection pool"""
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="crawler_pool", pool_size=self.pool_size, **self.config
            )
            logger.info(f"MySQL connection pool initialized, size: {self.pool_size}")
        except Error as e:
            logger.error(f"Failed to initialize MySQL connection pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Context manager: Get database connection"""
        if self.pool is None:
            self.initialize_pool()

        conn = None
        try:
            conn = self.pool.get_connection()
            yield conn
        except Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def create_tables(self):
        """Create necessary database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Create RSS sources table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS rss_sources (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        feed_url VARCHAR(512) UNIQUE NOT NULL,
                        title VARCHAR(255),
                        description TEXT,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_crawled_at TIMESTAMP NULL,
                        active BOOLEAN DEFAULT TRUE,
                        INDEX idx_feed_url (feed_url),
                        INDEX idx_active (active)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

                # Create articles table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS articles (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        url VARCHAR(512) NOT NULL,
                        final_url VARCHAR(512),
                        feed_url VARCHAR(512),
                        rss_title VARCHAR(512),
                        rss_published_at DATETIME NULL,
                        fetched_at DATETIME NOT NULL,
                        http_status INT,
                        error TEXT,

                        title VARCHAR(512),
                        author VARCHAR(255),
                        published_date VARCHAR(255),
                        language VARCHAR(10),
                        text_content LONGTEXT,

                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                        UNIQUE KEY idx_url_feed (url, feed_url),
                        INDEX idx_feed_url (feed_url),
                        INDEX idx_fetched_at (fetched_at),
                        INDEX idx_published (rss_published_at),
                        FULLTEXT idx_fulltext (title, text_content)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

                # Create fetch logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fetch_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        url VARCHAR(512) NOT NULL,
                        feed_url VARCHAR(512),
                        fetch_time DATETIME NOT NULL,
                        success BOOLEAN NOT NULL,
                        http_status INT,
                        error_message TEXT,
                        INDEX idx_url (url),
                        INDEX idx_fetch_time (fetch_time),
                        INDEX idx_success (success)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

                conn.commit()
                logger.info("Database tables created successfully")
            except Error as e:
                conn.rollback()
                logger.error(f"Failed to create tables: {e}")
                raise
            finally:
                cursor.close()

    def add_rss_source(
        self,
        feed_url: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Add RSS source"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO rss_sources (feed_url, title, description)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        title = VALUES(title),
                        description = VALUES(description)
                """,
                    (feed_url, title, description),
                )
                conn.commit()
                logger.info(f"RSS source added: {feed_url}")
                return True
            except Error as e:
                conn.rollback()
                logger.error(f"Failed to add RSS source: {e}")
                return False
            finally:
                cursor.close()

    def save_article(self, article: ArticleRecord) -> bool:
        """Save article record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Extract extracted fields
                extracted = article.extracted or {}
                title = extracted.get("title")
                author = extracted.get("author")
                date = extracted.get("date")
                language = extracted.get("language")
                text = extracted.get("text")

                # Convert time formats
                fetched_at = datetime.fromisoformat(
                    article.fetched_at.replace("Z", "+00:00")
                )
                rss_published = None
                if article.rss_published_at:
                    try:
                        rss_published = datetime.fromisoformat(
                            article.rss_published_at.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

                cursor.execute(
                    """
                    INSERT INTO articles (
                        url, final_url, feed_url, rss_title, rss_published_at,
                        fetched_at, http_status, error,
                        title, author, published_date, language, text_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        final_url = VALUES(final_url),
                        http_status = VALUES(http_status),
                        error = VALUES(error),
                        title = VALUES(title),
                        author = VALUES(author),
                        published_date = VALUES(published_date),
                        language = VALUES(language),
                        text_content = VALUES(text_content)
                """,
                    (
                        article.url,
                        article.final_url,
                        article.feed_url,
                        article.rss_title,
                        rss_published,
                        fetched_at,
                        article.http_status,
                        article.error,
                        title,
                        author,
                        date,
                        language,
                        text,
                    ),
                )

                conn.commit()
                return True
            except Error as e:
                conn.rollback()
                logger.error(f"Saving article failed {article.url}: {e}")
                return False
            finally:
                cursor.close()

    def save_article_metadata_only(self, article: ArticleRecord) -> Optional[int]:
        """
        Save only article metadata (without text_content) and return doc_id.
        This is used to get doc_id first before passing content to indexer.

        Args:
            article: ArticleRecord with metadata

        Returns:
            doc_id (article id) if successful, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Extract extracted fields (excluding text)
                extracted = article.extracted or {}
                title = extracted.get("title")
                author = extracted.get("author")
                date = extracted.get("date")
                language = extracted.get("language")

                # Convert time formats
                fetched_at = datetime.fromisoformat(
                    article.fetched_at.replace("Z", "+00:00")
                )
                rss_published = None
                if article.rss_published_at:
                    try:
                        rss_published = datetime.fromisoformat(
                            article.rss_published_at.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

                # Insert metadata only (text_content is NULL)
                cursor.execute(
                    """
                    INSERT INTO articles (
                        url, final_url, feed_url, rss_title, rss_published_at,
                        fetched_at, http_status, error,
                        title, author, published_date, language, text_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                    ON DUPLICATE KEY UPDATE
                        final_url = VALUES(final_url),
                        http_status = VALUES(http_status),
                        error = VALUES(error),
                        title = VALUES(title),
                        author = VALUES(author),
                        published_date = VALUES(published_date),
                        language = VALUES(language),
                        id = LAST_INSERT_ID(id)
                """,
                    (
                        article.url,
                        article.final_url,
                        article.feed_url,
                        article.rss_title,
                        rss_published,
                        fetched_at,
                        article.http_status,
                        article.error,
                        title,
                        author,
                        date,
                        language,
                    ),
                )

                # Get the doc_id (either newly inserted or existing)
                doc_id = cursor.lastrowid
                conn.commit()
                logger.info(f"Article metadata saved with doc_id: {doc_id}")
                return doc_id
            except Error as e:
                conn.rollback()
                logger.error(f"Saving article metadata failed {article.url}: {e}")
                return None
            finally:
                cursor.close()

    def update_article_content(self, doc_id: int, text_content: str) -> bool:
        """
        Update article text content by doc_id.
        This is called after content has been sent to indexer.

        Args:
            doc_id: Document ID
            text_content: Full text content

        Returns:
            True if successful, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE articles
                    SET text_content = %s
                    WHERE id = %s
                """,
                    (text_content, doc_id),
                )
                conn.commit()
                logger.info(f"Article content updated for doc_id: {doc_id}")
                return True
            except Error as e:
                conn.rollback()
                logger.error(
                    f"Updating article content failed for doc_id {doc_id}: {e}"
                )
                return False
            finally:
                cursor.close()

    def get_article_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """
        Get article by doc_id.

        Args:
            doc_id: Document ID

        Returns:
            Article record dict or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT * FROM articles WHERE id = %s
                """,
                    (doc_id,),
                )
                return cursor.fetchone()
            except Error as e:
                logger.error(f"Failed to get article by id {doc_id}: {e}")
                return None
            finally:
                cursor.close()

    def save_articles_batch(self, articles: List[ArticleRecord]) -> int:
        """Save articles in batch"""
        success_count = 0
        for article in articles:
            if self.save_article(article):
                success_count += 1
        return success_count

    def log_fetch(
        self,
        url: str,
        feed_url: str,
        success: bool,
        http_status: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Log fetch"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO fetch_logs (url, feed_url, fetch_time, success, http_status, error_message)
                    VALUES (%s, %s, NOW(), %s, %s, %s)
                """,
                    (url, feed_url, success, http_status, error_message),
                )
                conn.commit()
                return True
            except Error as e:
                conn.rollback()
                logger.error(f"Failed to log fetch: {e}")
                return False
            finally:
                cursor.close()

    def get_articles(
        self, feed_url: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get articles list"""
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                if feed_url:
                    cursor.execute(
                        """
                        SELECT * FROM articles
                        WHERE feed_url = %s
                        ORDER BY fetched_at DESC
                        LIMIT %s OFFSET %s
                    """,
                        (feed_url, limit, offset),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM articles
                        ORDER BY fetched_at DESC
                        LIMIT %s OFFSET %s
                    """,
                        (limit, offset),
                    )

                return cursor.fetchall()
            except Error as e:
                logger.error(f"Failed to get articles list: {e}")
                return []
            finally:
                cursor.close()

    def search_articles(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Full-text search articles"""
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT *, MATCH(title, text_content) AGAINST(%s IN NATURAL LANGUAGE MODE) as relevance
                    FROM articles
                    WHERE MATCH(title, text_content) AGAINST(%s IN NATURAL LANGUAGE MODE)
                    ORDER BY relevance DESC
                    LIMIT %s
                """,
                    (keyword, keyword, limit),
                )

                return cursor.fetchall()
            except Error as e:
                logger.error(f"Failed to search articles: {e}")
                return []
            finally:
                cursor.close()

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                stats = {}

                # Total articles count
                cursor.execute("SELECT COUNT(*) as count FROM articles")
                stats["total_articles"] = cursor.fetchone()["count"]

                # RSS sources count
                cursor.execute(
                    "SELECT COUNT(*) as count FROM rss_sources WHERE active = TRUE"
                )
                stats["active_sources"] = cursor.fetchone()["count"]

                # Success rate
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN success = TRUE THEN 1 ELSE 0 END) as success
                    FROM fetch_logs
                    WHERE fetch_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                """)
                result = cursor.fetchone()
                if result["total"] > 0:
                    stats["success_rate_24h"] = result["success"] / result["total"]
                else:
                    stats["success_rate_24h"] = 0

                return stats
            except Error as e:
                logger.error(f"Failed to get statistics: {e}")
                return {}
            finally:
                cursor.close()

    def close(self):
        """Close connection pool"""
        if self.pool:
            # MySQL connector does not have a direct method to close the connection pool
            # Connections will be automatically closed when the object is destroyed
            logger.info("MySQL connection pool closed")


# Useful Method
def create_mysql_db(
    host: str = "localhost",
    port: int = 3306,
    user: str = "ttds_app",
    password: str = "ttds#123",
    database: str = "ttds_search_engine",
    pool_size: int = 5,
) -> MySQLDatabase:
    """Create and initialise MySQL database instance"""
    db = MySQLDatabase(host, port, user, password, database, pool_size)
    db.initialize_pool()
    db.create_tables()
    return db
