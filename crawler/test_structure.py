#!/usr/bin/env python
"""
Quick structure validation script
Tests that all modules can be imported correctly
"""

import sys
from pathlib import Path

# Ensure we're in the crawler directory
crawler_dir = Path(__file__).parent
sys.path.insert(0, str(crawler_dir))


def test_imports():
    """Test all critical imports"""
    print("=" * 60)
    print("Testing New Project Structure")
    print("=" * 60)

    tests = []

    # Test 1: Config
    try:
        from src.config import CONFIG, MYSQL_CONFIG, INDEXER_CONFIG

        print("✓ Config imports successful")
        tests.append(True)
    except Exception as e:
        print(f"✗ Config import failed: {e}")
        tests.append(False)

    # Test 2: Core models
    try:
        from src.core.models import ArticleRecord, RssEntry, FetchResult

        print("✓ Core models imports successful")
        tests.append(True)
    except Exception as e:
        print(f"✗ Core models import failed: {e}")
        tests.append(False)

    # Test 3: Core modules
    try:
        from src.core.fetcher import fetch_html, build_session
        from src.core.rss_parser import parse_feed
        from src.core.extractor import extract_main_text
        from src.core.pipeline import run_feed_pipeline
        from src.core.utils import utc_now_iso, polite_sleep

        print("✓ Core modules imports successful")
        tests.append(True)
    except Exception as e:
        print(f"✗ Core modules import failed: {e}")
        tests.append(False)

    # Test 4: Storage modules
    try:
        from src.storage.db_mysql import MySQLDatabase, create_mysql_db
        from src.storage.output import write_jsonl

        print("✓ Storage modules imports successful")
        tests.append(True)
    except Exception as e:
        print(f"✗ Storage modules import failed: {e}")
        tests.append(False)

    # Test 5: Integration modules
    try:
        from src.integration.coordinator import CrawlerCoordinator, create_coordinator
        from src.integration.indexer_interface import FileBasedIndexer, create_indexer

        print("✓ Integration modules imports successful")
        tests.append(True)
    except Exception as e:
        print(f"✗ Integration modules import failed: {e}")
        tests.append(False)

    # Test 6: CLI modules
    try:
        from src.cli import main
        from src.cli import main_with_coordinator

        print("✓ CLI modules imports successful")
        tests.append(True)
    except Exception as e:
        print(f"✗ CLI modules import failed: {e}")
        tests.append(False)

    print("=" * 60)
    passed = sum(tests)
    total = len(tests)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All imports successful! Structure is correct.")
        return 0
    else:
        print("✗ Some imports failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = test_imports()
    sys.exit(exit_code)
