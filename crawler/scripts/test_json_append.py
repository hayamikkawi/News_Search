"""
Test script: JSON append mode and deduplication features
Demonstrates how to use append mode in scheduled tasks
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.integration.indexer_interface import FileBasedIndexer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_append_mode():
    """Test append mode"""
    logger.info("=" * 70)
    logger.info("JSON append mode test")
    logger.info("=" * 70)

    # Create test output directory
    test_output_dir = project_root / "output" / "test_json"
    test_output_dir.mkdir(parents=True, exist_ok=True)

    test_file = "test_docs.json"
    test_file_path = test_output_dir / test_file

    # Clean up previous test file
    if test_file_path.exists():
        test_file_path.unlink()
        logger.info(f"Cleaned up previous test file: {test_file_path}")

    logger.info(f"\nTest output: {test_file_path}")
    logger.info("")

    # ===== First run: Add 5 articles =====
    logger.info("=" * 70)
    logger.info("First run: Add 5 articles")
    logger.info("=" * 70)

    indexer1 = FileBasedIndexer(
        output_dir=str(test_output_dir),
        output_filename=test_file,
        dedup_threshold_mb=1,  # Set small threshold to test streaming
    )

    for i in range(1, 6):
        indexer1.send_document(
            doc_id=i,
            content=f"This is the content of article {i}. " * 20,
            metadata={"title": f"Article {i}", "url": f"https://example.com/article{i}"},
        )

    indexer1.flush(mode="append")  # Default append mode

    # View stats
    stats = indexer1.get_file_stats()
    logger.info(f"\nStats: {stats}")

    # ===== Second run: Add 3 new articles + update 1 =====
    logger.info("\n" + "=" * 70)
    logger.info("Second run: Add 3 new articles + update 1")
    logger.info("=" * 70)

    indexer2 = FileBasedIndexer(output_dir=str(test_output_dir), output_filename=test_file)

    # Add new articles 6, 7, 8
    for i in range(6, 9):
        indexer2.send_document(
            doc_id=i,
            content=f"This is the content of article {i}. " * 20,
            metadata={"title": f"Article {i}", "url": f"https://example.com/article{i}"},
        )

    # Update article 3 (content updated)
    indexer2.send_document(
        doc_id=3,
        content=f"This is the UPDATED content of article 3. " * 25,
        metadata={"title": f"Article 3 (Updated)", "url": f"https://example.com/article3"},
    )

    indexer2.flush(mode="append")  # Append and auto deduplicate

    # View stats
    stats = indexer2.get_file_stats()
    logger.info(f"\nStats: {stats}")

    # Verify results
    with open(test_file_path, "r", encoding="utf-8") as f:
        all_docs = json.load(f)

    logger.info(f"\nFinal results:")
    logger.info(f"  - Total documents: {len(all_docs)}")
    logger.info(f"  - Document ID list: {sorted([doc['id'] for doc in all_docs])}")

    # Check if article 3 was updated
    article3 = [doc for doc in all_docs if doc["id"] == 3][0]
    is_updated = "UPDATED" in article3["content"]
    logger.info(f"  - Article 3 updated: {is_updated}")

    # ===== Third run: Test fast append mode (allow duplicates) =====
    logger.info("\n" + "=" * 70)
    logger.info("Third run: Test fast append mode (no deduplication)")
    logger.info("=" * 70)

    indexer3 = FileBasedIndexer(output_dir=str(test_output_dir), output_filename=test_file)

    # Add duplicate articles (simulate high-frequency updates)
    for i in range(1, 4):
        indexer3.send_document(
            doc_id=i,
            content=f"Duplicate content {i}. " * 10,
            metadata={"title": f"Duplicate Article {i}", "url": f"https://example.com/article{i}"},
        )

    indexer3.flush(mode="append_only")  # Fast append, no deduplication

    stats = indexer3.get_file_stats()
    logger.info(f"\nStats: {stats}")
    logger.info(f"  - Has duplicates: {stats['has_duplicates']}")
    logger.info(f"  - Duplicate count: {stats['duplicate_count']}")

    # ===== Fourth run: Manual deduplication =====
    logger.info("\n" + "=" * 70)
    logger.info("Fourth run: Manual deduplication")
    logger.info("=" * 70)

    indexer4 = FileBasedIndexer(output_dir=str(test_output_dir), output_filename=test_file)

    indexer4.dedup_file()

    stats = indexer4.get_file_stats()
    logger.info(f"\nStats after deduplication: {stats}")

    # ===== Performance test (optional) =====
    logger.info("\n" + "=" * 70)
    logger.info("Performance test: 1000 articles")
    logger.info("=" * 70)

    perf_file = "test_perf.json"
    perf_indexer = FileBasedIndexer(
        output_dir=str(test_output_dir),
        output_filename=perf_file,
        dedup_threshold_mb=1,  # Force streaming processing
    )

    # Cleanup
    perf_file_path = test_output_dir / perf_file
    if perf_file_path.exists():
        perf_file_path.unlink()

    import time

    # First add 1000 articles
    logger.info("Adding 1000 articles...")
    start = time.time()
    for i in range(1, 1001):
        perf_indexer.send_document(doc_id=i, content=f"Content {i}. " * 50, metadata={"title": f"Article {i}"})
    perf_indexer.flush(mode="append")
    elapsed = time.time() - start
    logger.info(f"  Elapsed time: {elapsed:.2f} seconds")

    # Append 500 new articles + update 100 articles
    logger.info("\nAppending 500 new + updating 100...")
    perf_indexer2 = FileBasedIndexer(output_dir=str(test_output_dir), output_filename=perf_file)

    start = time.time()
    for i in range(1001, 1501):  # New articles
        perf_indexer2.send_document(doc_id=i, content=f"Content {i}. " * 50, metadata={"title": f"Article {i}"})
    for i in range(1, 101):  # Update first 100 articles
        perf_indexer2.send_document(
            doc_id=i, content=f"UPDATED Content {i}. " * 50, metadata={"title": f"UPDATED Article {i}"}
        )
    perf_indexer2.flush(mode="append")
    elapsed = time.time() - start
    logger.info(f"  Elapsed time: {elapsed:.2f} seconds")

    # Final stats
    stats = perf_indexer2.get_file_stats()
    logger.info(f"\nFinal stats: {stats}")

    logger.info("\n" + "=" * 70)
    logger.info("Test completed!")
    logger.info("=" * 70)
    logger.info(f"\nTest file location: {test_output_dir}")
    logger.info("You can manually check the generated JSON files")


if __name__ == "__main__":
    try:
        test_append_mode()
    except KeyboardInterrupt:
        logger.info("\nUser interrupted the test")
    except Exception as e:
        logger.error(f"\nTest error: {e}", exc_info=True)
