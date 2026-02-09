"""
Tool: Check and fix duplicate IDs in JSON file
Ensures data quality for Indexer input files
"""

import sys
import json
import logging
from pathlib import Path
from collections import Counter

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import INDEXER_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_duplicates(file_path: str = None):
    """Check for duplicate doc_id in JSON file"""

    if file_path is None:
        file_path = Path(INDEXER_CONFIG.output_dir) / INDEXER_CONFIG.output_filename
    else:
        file_path = Path(file_path)

    logger.info("=" * 70)
    logger.info("Check for duplicate IDs in JSON file")
    logger.info("=" * 70)
    logger.info(f"File path: {file_path}")

    if not file_path.exists():
        logger.error(f"File does not exist: {file_path}")
        return False

    try:
        # Read file
        with open(file_path, "r", encoding="utf-8") as f:
            docs = json.load(f)

        total_docs = len(docs)
        logger.info(f"Total documents: {total_docs}")

        # Count ID occurrences
        doc_ids = [doc["id"] for doc in docs]
        id_counts = Counter(doc_ids)

        # Find duplicate IDs
        duplicates = {doc_id: count for doc_id, count in id_counts.items() if count > 1}

        if not duplicates:
            logger.info("No duplicate IDs found, file is healthy!")
            return True

        # Report duplicates
        logger.warning(f"Found {len(duplicates)} duplicate IDs!")
        logger.warning(f"Total duplicate documents: {sum(duplicates.values()) - len(duplicates)}")

        # Show top 10 duplicate IDs
        logger.warning("\nDuplicate ID details (top 10):")
        for i, (doc_id, count) in enumerate(sorted(duplicates.items())[:10], 1):
            logger.warning(f"  {i}. ID {doc_id}: Occurs {count} times")

        if len(duplicates) > 10:
            logger.warning(f"  ... {len(duplicates) - 10} more duplicate IDs not shown")

        # Warning
        logger.warning("\nWarning: Duplicate IDs may cause errors in the Indexer!")
        logger.warning("It is recommended to run the deduplication fix immediately:")
        logger.warning(f"  python {__file__} --fix")

        return False

    except Exception as e:
        logger.error(f"Check failed: {e}")
        return False


def fix_duplicates(file_path: str = None, backup: bool = True):
    """Fix duplicate IDs in JSON file (keep the last occurrence)"""

    if file_path is None:
        file_path = Path(INDEXER_CONFIG.output_dir) / INDEXER_CONFIG.output_filename
    else:
        file_path = Path(file_path)

    logger.info("=" * 70)
    logger.info("Fix duplicate IDs in JSON file")
    logger.info("=" * 70)
    logger.info(f"File path: {file_path}")

    if not file_path.exists():
        logger.error(f"File does not exist: {file_path}")
        return False

    try:
        # Backup original file
        if backup:
            backup_path = file_path.with_suffix(".json.backup")
            import shutil

            shutil.copy2(file_path, backup_path)
            logger.info(f"Backed up original file to: {backup_path}")

        # Read file
        with open(file_path, "r", encoding="utf-8") as f:
            docs = json.load(f)

        original_count = len(docs)
        logger.info(f"Original document count: {original_count}")

        # Deduplicate (keep the last occurrence, implemented via dictionary)
        doc_dict = {}
        for doc in docs:
            doc_dict[doc["id"]] = doc

        deduped_docs = sorted(doc_dict.values(), key=lambda x: x["id"])
        final_count = len(deduped_docs)
        removed_count = original_count - final_count

        # Write back to file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(deduped_docs, f, ensure_ascii=False, indent=2)

        logger.info(f"Fix completed!")
        logger.info(f"  - Removed duplicates: {removed_count}")
        logger.info(f"  - Final document count: {final_count}")
        logger.info(f"  - File updated: {file_path}")

        return True

    except Exception as e:
        logger.error(f"Fix failed: {e}")
        return False


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Check and fix duplicate IDs in JSON file")
    parser.add_argument("--fix", action="store_true", help="Fix duplicate IDs (default is to only check)")
    parser.add_argument("--no-backup", action="store_true", help="Do not backup when fixing (not recommended)")
    parser.add_argument("--file", type=str, help="Specify JSON file path (default uses config)")

    args = parser.parse_args()

    if args.fix:
        success = fix_duplicates(args.file, backup=not args.no_backup)
        if success:
            # Check again after fixing
            logger.info("\nVerifying fix results...")
            check_duplicates(args.file)
    else:
        check_duplicates(args.file)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nUser interrupted")
    except Exception as e:
        logger.error(f"\nError occurred: {e}", exc_info=True)
