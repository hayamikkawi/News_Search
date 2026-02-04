"""
数据库验证查询脚本
用于检查 crawler 存储到数据库的数据
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import MYSQL_CONFIG
from crawler.db_mysql import create_mysql_db
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def verify_database_content():
    """Verify database content"""

    logger.info("=" * 70)
    logger.info("Database Content Verification")
    logger.info("=" * 70)

    try:
        # Connect to database
        logger.info("\nConnecting to database...")
        db = create_mysql_db(
            host=MYSQL_CONFIG.host,
            port=MYSQL_CONFIG.port,
            user=MYSQL_CONFIG.user,
            password=MYSQL_CONFIG.password,
            database=MYSQL_CONFIG.database,
        )
        logger.info("[OK] Database connected successfully")

        # 使用上下文管理器获取连接
        with db.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # 1. Check RSS sources
            logger.info("\n" + "-" * 70)
            logger.info("1. RSS Sources List")
            logger.info("-" * 70)
            cursor.execute("""
                SELECT id, feed_url, title, description,
                       active, added_at, last_crawled_at
                FROM rss_sources
                ORDER BY added_at DESC
                LIMIT 10
            """)
            sources = cursor.fetchall()

            if sources:
                logger.info(f"Found {len(sources)} RSS source(s):")
                for source in sources:
                    logger.info(f"\n  ID: {source['id']}")
                    logger.info(f"  Title: {source['title']}")
                    logger.info(f"  URL: {source['feed_url']}")
                    logger.info(f"  Active: {source['active']}")
                    logger.info(f"  Created at: {source['added_at']}")
                    logger.info(f"  Last crawled: {source['last_crawled_at']}")
            else:
                logger.warning("  No RSS sources found")

            # 2. Check total articles count
            logger.info("\n" + "-" * 70)
            logger.info("2. Articles Statistics")
            logger.info("-" * 70)
            cursor.execute("SELECT COUNT(*) as total FROM articles")
            result = cursor.fetchone()
            total_articles = result["total"]
            logger.info(f"Total articles: {total_articles}")

            # 3. Recent articles
            logger.info("\n" + "-" * 70)
            logger.info("3. Recent Articles (Top 10)")
            logger.info("-" * 70)
            cursor.execute("""
                SELECT
                    id as doc_id,
                    url,
                    title,
                    author,
                    published_date,
                    language,
                    CASE
                        WHEN text_content IS NULL THEN 'No'
                        ELSE 'Yes'
                    END as has_content,
                    created_at
                FROM articles
                ORDER BY created_at DESC
                LIMIT 10
            """)
            articles = cursor.fetchall()

            if articles:
                for i, article in enumerate(articles, 1):
                    logger.info(f"\n  Article {i}:")
                    logger.info(f"    doc_id: {article['doc_id']}")
                    logger.info(f"    Title: {article['title']}")
                    logger.info(f"    Author: {article['author'] or 'N/A'}")
                    logger.info(f"    URL: {article['url'][:70]}...")
                    logger.info(f"    Published: {article['published_date']}")
                    logger.info(f"    Language: {article['language']}")
                    logger.info(f"    Has content: {article['has_content']}")
                    logger.info(f"    Created at: {article['created_at']}")
            else:
                logger.warning("  No articles found")

            # 4. Articles by RSS source
            logger.info("\n" + "-" * 70)
            logger.info("4. Articles Statistics by RSS Source")
            logger.info("-" * 70)
            cursor.execute("""
                SELECT
                    rs.id as source_id,
                    rs.title as source_title,
                    rs.feed_url,
                    COUNT(a.id) as article_count,
                    MAX(a.created_at) as latest_article
                FROM rss_sources rs
                LEFT JOIN articles a ON rs.feed_url = a.feed_url
                GROUP BY rs.id, rs.title, rs.feed_url
                ORDER BY article_count DESC
            """)
            stats = cursor.fetchall()

            if stats:
                for stat in stats:
                    logger.info(f"\n  RSS Source: {stat['source_title']}")
                    logger.info(f"    URL: {stat['feed_url']}")
                    logger.info(f"    Article count: {stat['article_count']}")
                    logger.info(f"    Latest article: {stat['latest_article']}")
            else:
                logger.warning("  No statistics data found")

            # 5. Language distribution
            logger.info("\n" + "-" * 70)
            logger.info("5. Language Distribution")
            logger.info("-" * 70)
            cursor.execute("""
                SELECT
                    language,
                    COUNT(*) as count
                FROM articles
                GROUP BY language
                ORDER BY count DESC
            """)
            languages = cursor.fetchall()

            if languages:
                for lang in languages:
                    logger.info(f"  {lang['language'] or 'Unknown'}: {lang['count']} article(s)")
            else:
                logger.warning("  No language data found")

            # 6. Check content storage
            logger.info("\n" + "-" * 70)
            logger.info("6. Content Storage Status")
            logger.info("-" * 70)
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN text_content IS NOT NULL THEN 1 ELSE 0 END) as with_content,
                    SUM(CASE WHEN text_content IS NULL THEN 1 ELSE 0 END) as without_content,
                    COUNT(*) as total
                FROM articles
            """)
            content_stats = cursor.fetchone()

            logger.info(f"  With content: {content_stats['with_content']}")
            logger.info(f"  Without content: {content_stats['without_content']}")
            logger.info(f"  Total: {content_stats['total']}")

            if content_stats["total"] > 0:
                percentage = (content_stats["with_content"] / content_stats["total"]) * 100
                logger.info(f"  Content storage rate: {percentage:.1f}%")

            # 7. Recent hour articles
            logger.info("\n" + "-" * 70)
            logger.info("7. Articles Created in Last Hour")
            logger.info("-" * 70)
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM articles
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """)
            recent = cursor.fetchone()
            logger.info(f"  Last hour: {recent['count']} article(s)")

            cursor.close()

        logger.info("\n" + "=" * 70)
        logger.info("[OK] Database verification completed")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"\n[FAILED] Database verification failed: {e}", exc_info=True)


def main():
    """Main function"""
    try:
        verify_database_content()
    except KeyboardInterrupt:
        logger.info("\nUser interrupted")
    except Exception as e:
        logger.error(f"\nException occurred: {e}", exc_info=True)


if __name__ == "__main__":
    main()
