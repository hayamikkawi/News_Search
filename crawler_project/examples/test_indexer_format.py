"""
Test FileBasedIndexer generates the format required by the Indexer
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from crawler.indexer_interface import create_indexer
from crawler.models import ArticleRecord
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_file_based_indexer_format():
    """Test FileBasedIndexer generates the correct format"""

    logger.info("=" * 60)
    logger.info("Testing FileBasedIndexer Output Format")
    logger.info("=" * 60)

    # Create test output directory
    output_dir = "./test_indexer_output"
    output_filename = "test_docs.json"

    # Create FileBasedIndexer
    logger.info(f"\n1. Creating FileBasedIndexer...")
    logger.info(f"   Output: {output_dir}/{output_filename}")
    indexer = create_indexer(output_dir=output_dir, output_filename=output_filename)
    logger.info("Indexer created")

    # Create test documents
    logger.info("\n2. Creating test documents...")
    test_docs = [
        {
            "doc_id": 1,
            "content": "Artificial intelligence is transforming healthcare by enabling faster and more accurate diagnoses. Machine learning models can analyze medical images, patient records, and genetic data to identify patterns that humans might miss.",
            "metadata": {
                "title": "AI Transforms Healthcare Diagnostics",
                "author": "Dr. Jane Smith",
                "date": "2026-02-04",
                "url": "https://example.com/article/1",
            },
        },
        {
            "doc_id": 2,
            "content": "Renewable energy storage has long been a challenge. Recent breakthroughs in solid-state batteries and alternative materials have significantly improved storage capacity and lifespan, paving the way for a cleaner energy future.",
            "metadata": {
                "title": "Breakthroughs in Energy Storage",
                "author": "Prof. John Doe",
                "date": "2026-02-03",
                "url": "https://example.com/article/2",
                "description": "New battery technologies revolutionize renewable energy storage.",
            },
        },
        {
            "doc_id": 3,
            "content": "Remote work has become the new normal for many organizations. Studies show increased productivity and better work-life balance, although companies must invest in collaboration tools to maintain team cohesion.",
            "metadata": {
                "title": "The Future of Remote Work",
                "author": "Sarah Johnson",
                "date": "2026-02-02",
                "url": "https://example.com/article/3",
            },
        },
    ]

    # Send documents to indexer
    logger.info("\n3. Sending documents to indexer...")
    for doc in test_docs:
        success = indexer.send_document(doc_id=doc["doc_id"], content=doc["content"], metadata=doc["metadata"])
        if success:
            logger.info(f"   Document {doc['doc_id']}: {doc['metadata']['title']}")
        else:
            logger.error(f"   Failed to send document {doc['doc_id']}")

    # Show current accumulated document count
    doc_count = indexer.get_document_count()
    logger.info(f"\n4. Documents in buffer: {doc_count}")

    # Flush to file
    logger.info("\n5. Flushing documents to file...")
    if indexer.flush():
        logger.info("Documents flushed successfully")
    else:
        logger.error("Failed to flush documents")

    # Verify output format
    logger.info("\n6. Verifying output format...")
    output_file = Path(output_dir) / output_filename
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info(f"Output file created: {output_file}")
        logger.info(f"Number of documents: {len(data)}")

        # Check format
        logger.info("\n7. Checking document format...")
        required_fields = ["id", "title", "description", "content"]
        format_ok = True

        for i, doc in enumerate(data):
            missing_fields = [field for field in required_fields if field not in doc]
            if missing_fields:
                logger.error(f"   Document {i}: missing fields {missing_fields}")
                format_ok = False
            else:
                logger.info(f"   Document {doc['id']}: {doc['title'][:50]}...")

        if format_ok:
            logger.info("\nAll documents have correct format!")
            logger.info("\n8. Sample document structure:")
            logger.info(json.dumps(data[0], indent=2, ensure_ascii=False)[:500] + "...")
        else:
            logger.error("\nSome documents have incorrect format")

    else:
        logger.error(f"Output file not found: {output_file}")

    logger.info("\n" + "=" * 60)
    logger.info("Test completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        test_file_based_indexer_format()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
