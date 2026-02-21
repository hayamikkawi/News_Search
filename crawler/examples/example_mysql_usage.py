"""
MySQL Module Usage Example:
Demonstrates how to use the db_mysql module for data storage and querying
"""

import sys
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.db_mysql import create_mysql_db
from src.core.models import ArticleRecord
from src.config import MYSQL_CONFIG
from datetime import datetime


def main():
    """Main function: Demonstrates usage of the MySQL module"""

    # 1. Create database instance
    print("Initializing MySQL connection...")
    db = create_mysql_db(
        host=MYSQL_CONFIG.host,
        port=MYSQL_CONFIG.port,
        user=MYSQL_CONFIG.user,
        password=MYSQL_CONFIG.password,
        database=MYSQL_CONFIG.database,
        pool_size=MYSQL_CONFIG.pool_size,
    )
    print("MySQL connection established, tables created")

    # 2. Add RSS source
    print("\nAdding RSS source...")
    db.add_rss_source(
        feed_url="https://example.com/rss",
        title="Example News Site",
        description="Example RSS feed",
    )
    print("RSS source added")

    # 3. Save article example
    print("\nSaving article record...")
    article = ArticleRecord(
        url="https://example.com/article/1",
        final_url="https://example.com/article/1",
        feed_url="https://example.com/rss",
        rss_title="Example Article Title",
        rss_published_at=datetime.now().isoformat(),
        fetched_at=datetime.now().isoformat(),
        http_status=200,
        error=None,
        extracted={
            "title": "This is a sample article",
            "author": "John Doe",
            "date": "2026-02-04",
            "language": "en",
            "text": "This is the main content of the article, containing the primary textual information." * 20,
        },
    )

    if db.save_article(article):
        print("Article saved successfully")

    # 4. Log fetch
    print("\nLogging fetch...")
    db.log_fetch(
        url="https://example.com/article/1",
        feed_url="https://example.com/rss",
        success=True,
        http_status=200,
    )
    print("Fetch logged")

    # 5. Query articles
    print("\nQuerying latest articles...")
    articles = db.get_articles(limit=5)
    print(f"Found {len(articles)} articles")
    for i, art in enumerate(articles, 1):
        print(f"  {i}. {art['title']} ({art['url']})")

    # 6. Full-text search
    print("\nPerforming full-text search...")
    results = db.search_articles("example", limit=10)
    print(f"Found {len(results)} results")

    # 7. Get statistics
    print("\nGetting statistics...")
    stats = db.get_statistics()
    print("Statistics:")
    print(f"  Total articles: {stats.get('total_articles', 0)}")
    print(f"  Active sources: {stats.get('active_sources', 0)}")
    print(f"  24h success rate: {stats.get('success_rate_24h', 0):.2%}")

    # 8. Close connection
    db.close()
    print("\nDatabase connection closed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
