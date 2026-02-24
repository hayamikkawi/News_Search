#!/usr/bin/env python3
"""
Create database tables in test_db for testing.
"""

import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "crawler" / "src"))

try:
    from crawler.src.storage.db_mysql import MySQLDatabase
    from crawler.src.config import MYSQL_CONFIG
except ImportError as e:
    # Try alternative import path
    try:
        from storage.db_mysql import MySQLDatabase
        from config import MYSQL_CONFIG
    except ImportError:
        print(f"Error importing crawler modules: {e}")
        sys.exit(1)

def create_test_tables():
    """Create tables in test database."""
    # Use test database instead of production
    config = {
        "host": MYSQL_CONFIG.host,
        "port": MYSQL_CONFIG.port,
        "user": MYSQL_CONFIG.user,
        "password": MYSQL_CONFIG.password,
        "database": "test_db",  # Use test database
        "pool_size": 5
    }

    print(f"Connecting to MySQL at {config['host']}:{config['port']}/{config['database']}")

    try:
        db = MySQLDatabase(**config)
        db.initialize_pool()
        print("Database connection established")

        # Create tables
        print("Creating tables...")
        db.create_tables()
        print("Tables created successfully")

        # Verify tables exist
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"Tables in test_db: {[table[0] for table in tables]}")
            cursor.close()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_test_tables()