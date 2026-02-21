"""
Test script: Validate ID jump issue fix
Run the same RSS source multiple times and check if IDs still jump
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import MYSQL_CONFIG
from src.storage.db_mysql import MySQLDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_id_gap():
    """Test ID jump issue"""
    logger.info("=" * 60)
    logger.info("Testing ID Jump Issue")
    logger.info("=" * 60)

    # Connect to database
    database = MySQLDatabase(
        host=MYSQL_CONFIG.host,
        port=MYSQL_CONFIG.port,
        user=MYSQL_CONFIG.user,
        password=MYSQL_CONFIG.password,
        database=MYSQL_CONFIG.database,
        pool_size=MYSQL_CONFIG.pool_size,
    )

    database.initialize_pool()

    # Query current max ID
    with database.get_connection() as conn:
        cursor = conn.cursor()

        # Get current max ID
        cursor.execute("SELECT MAX(id) FROM articles")
        max_id_before = cursor.fetchone()[0] or 0

        # Get total record count
        cursor.execute("SELECT COUNT(*) FROM articles")
        count = cursor.fetchone()[0]

        cursor.close()

    logger.info("Current database status:")
    logger.info(f"  - Max ID: {max_id_before}")
    logger.info(f"  - Total records: {count}")

    if max_id_before > 0:
        gap = max_id_before - count
        gap_rate = (gap / max_id_before) * 100
        logger.info(f"  - ID gap: {gap} (Gap rate: {gap_rate:.2f}%)")

    logger.info("")
    logger.info("Testing suggestions:")
    logger.info("1. Run the crawler script: python crawler/scripts/validate_crawler.py")
    logger.info("2. Run this script again to check ID changes")
    logger.info("3. Run the crawler multiple times to check if duplicate articles increase IDs")
    logger.info("")
    logger.info("Expected results:")
    logger.info("  ✓ Duplicate articles do not increase the max ID")
    logger.info("  ✓ Only new articles are assigned new consecutive IDs")
    logger.info("  ✓ Logs show: 'Article already exists, updated metadata for doc_id: X'")


if __name__ == "__main__":
    test_id_gap()
