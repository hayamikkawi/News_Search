"""
Indexer Interface Module
File-based implementation to communicate with the Indexer component
Generates JSON array format files as required by the Indexer

Supports:
- Append mode: Fast append for incremental updates
- Deduplication: Automatic dedup based on doc_id
- Streaming: Handle large files (millions of documents)
"""

import logging
import json
import os
import tempfile
from typing import List, Dict, Set
from datetime import datetime


logger = logging.getLogger(__name__)


class FileBasedIndexer:
    """
    File-based Indexer interface (adapted to the actual input format of the Indexer team)
    The expected input format by the Indexer team:
    [
        {
            "id": 1,
            "title": "Article Title",
            "description": "Article Description/Summary",
            "content": "Full article text content..."
        }
    ]
    This implementation accumulates all documents and writes them to a single JSON file for the Indexer to read when flush() is called.
    """

    def __init__(self, output_dir: str, output_filename: str = "docs.json", dedup_threshold_mb: int = 100):
        """
        Initialize the file-based Indexer

        Args:
            output_dir: Output directory path
            output_filename: Output file name (default "docs.json")
            dedup_threshold_mb: File size threshold (MB) for choosing dedup strategy.
                               Files smaller than this use in-memory dedup (fast),
                               larger files use streaming dedup (memory-efficient)
        """
        self.output_dir = output_dir
        self.output_filename = output_filename
        self.documents = []  # Accumulated document list
        self.dedup_threshold_mb = dedup_threshold_mb
        os.makedirs(output_dir, exist_ok=True)

    def send_document(self, doc_id: int, content: str, metadata: dict = None) -> bool:
        """
        Accumulate documents in memory, waiting for batch write

        Convert the document to the format expected by the Indexer:
        - id: doc_id
        - title: extracted from metadata
        - description: extracted from metadata (if not present, use the first 200 characters of content)
        - content: full text content
        """
        try:
            metadata = metadata or {}

            # Extract or generate description (summary)
            description = metadata.get("description")
            if not description:
                # If no description is provided, use the first 200 characters of content as the summary
                description = content[:200] + "..." if len(content) > 200 else content

            # Construct document in the format expected by the Indexer
            document = {
                "id": doc_id,
                "title": metadata.get("title", ""),
                "description": description,
                "content": content,
            }

            self.documents.append(document)
            logger.info(f"Document {doc_id} added to batch (total: {len(self.documents)})")
            return True
        except Exception as e:
            logger.error(f"Error adding document {doc_id} to batch: {e}")
            return False

    def flush(self, mode: str = "append") -> bool:
        """
        Write all accumulated documents to a JSON file

        Args:
            mode: "append" (default, merge with existing and dedup - RECOMMENDED),
                  "overwrite" (replace existing file),
                  "append_only" (fast append without dedup - USE WITH CAUTION)

        Returns:
            True if successful, False otherwise

        IMPORTANT: If your Indexer cannot handle duplicate IDs correctly,
                   you MUST use "append" mode to ensure deduplication.
                   "append_only" is only safe if followed by periodic dedup_file().
        """
        try:
            if not self.documents:
                logger.warning("No documents to flush")
                return True

            file_path = os.path.join(self.output_dir, self.output_filename)

            if mode == "new_file":
                return self._flush_new_file()
            elif mode == "overwrite":
                return self._flush_overwrite(file_path)
            elif mode == "append":
                return self._flush_append_with_dedup(file_path)
            elif mode == "append_only":
                return self._flush_append_only(file_path)
            else:
                raise ValueError(f"Unknown flush mode: {mode}")

        except Exception as e:
            logger.error(f"Error flushing documents to file: {e}")
            return False

    def _flush_new_file(self) -> bool:
        try:
            filename = self._make_timestamp_name(prefix="docs")
            final_path = os.path.join(self.output_dir, filename)

            self._atomic_write_json(final_path, self.documents)

            logger.info(f"New-file flush: Flushed {len(self.documents)} documents to {final_path}")
            self.clear()
            return True
        except Exception as e:
            logger.error(f"New-file flush failed: {e}")
            return False

    def _flush_overwrite(self, file_path: str) -> bool:
        """Overwrite mode: Replace entire file (original behavior)"""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)

        logger.info(f"Overwrite: Flushed {len(self.documents)} documents to {file_path}")
        return True

    def _flush_append_with_dedup(self, file_path: str) -> bool:
        """
        Append mode with automatic deduplication.
        Strategy depends on file size:
        - Small files: Load into memory and dedup
        - Large files: Stream processing with temp file
        """
        if not os.path.exists(file_path):
            # File doesn't exist, just write
            return self._flush_overwrite(file_path)

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if file_size_mb < self.dedup_threshold_mb:
            return self._dedup_in_memory(file_path)
        else:
            return self._dedup_streaming(file_path)

    def _dedup_in_memory(self, file_path: str) -> bool:
        """
        In-memory deduplication for small-to-medium files (<100MB default).
        Fast but requires loading entire file into memory.
        """
        try:
            # Load existing documents
            with open(file_path, "r", encoding="utf-8") as f:
                existing_docs = json.load(f)

            # Build ID -> document mapping (later entries override earlier ones)
            doc_dict = {doc["id"]: doc for doc in existing_docs}

            # Add/update with new documents
            new_count = 0
            updated_count = 0
            for new_doc in self.documents:
                if new_doc["id"] in doc_dict:
                    updated_count += 1
                else:
                    new_count += 1
                doc_dict[new_doc["id"]] = new_doc

            # Convert back to list and sort by ID
            all_docs = sorted(doc_dict.values(), key=lambda x: x["id"])

            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(all_docs, f, ensure_ascii=False, indent=2)

            logger.info(f"In-memory dedup: {new_count} new, {updated_count} updated, total {len(all_docs)} documents")
            return True

        except Exception as e:
            logger.error(f"In-memory dedup failed: {e}")
            return False

    def _dedup_streaming(self, file_path: str) -> bool:
        """
        Streaming deduplication for large files (>100MB default).
        Memory-efficient but slower. Uses temporary file.
        """
        try:
            logger.info(f"Using streaming dedup for large file ")

            # Build ID set from new documents
            new_docs_dict = {doc["id"]: doc for doc in self.documents}
            processed_ids: Set[int] = set()

            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix=".json", dir=self.output_dir)

            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_f:
                    temp_f.write("[\n")

                    first_doc = True
                    new_count = 0
                    updated_count = 0
                    kept_count = 0

                    # Stream read existing file
                    with open(file_path, "r", encoding="utf-8") as f:
                        existing_docs = json.load(f)  # Still need to load for array format

                        for doc in existing_docs:
                            doc_id = doc["id"]

                            if doc_id in new_docs_dict:
                                # Update: use new version
                                doc_to_write = new_docs_dict[doc_id]
                                updated_count += 1
                                processed_ids.add(doc_id)
                            else:
                                # Keep existing
                                doc_to_write = doc
                                kept_count += 1

                            # Write document
                            if not first_doc:
                                temp_f.write(",\n")
                            json.dump(doc_to_write, temp_f, ensure_ascii=False)
                            first_doc = False

                    # Append truly new documents
                    for doc_id, doc in new_docs_dict.items():
                        if doc_id not in processed_ids:
                            if not first_doc:
                                temp_f.write(",\n")
                            json.dump(doc, temp_f, ensure_ascii=False)
                            new_count += 1
                            first_doc = False

                    temp_f.write("\n]")

                # Replace original file with temp file
                os.replace(temp_path, file_path)

                total = kept_count + updated_count + new_count
                logger.info(
                    f"Streaming dedup: {new_count} new, {updated_count} updated, "
                    f"{kept_count} kept, total {total} documents"
                )
                return True

            except Exception as e:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e

        except Exception as e:
            logger.error(f"Streaming dedup failed: {e}")
            return False

    def _flush_append_only(self, file_path: str) -> bool:
        """
        Fast append mode: NO deduplication.
        Appends documents to JSON array. Fast but may create duplicates.

        WARNING: Only use this mode if:
        1. Your Indexer can handle duplicate IDs, OR
        2. You will run dedup_file() before Indexer reads the file

        For most use cases, use "append" mode instead.
        """
        try:
            if not os.path.exists(file_path):
                return self._flush_overwrite(file_path)

            # Read existing file
            with open(file_path, "r", encoding="utf-8") as f:
                existing_docs = json.load(f)

            # Simply append
            existing_docs.extend(self.documents)

            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing_docs, f, ensure_ascii=False, indent=2)

            logger.info(
                f"Append-only: Added {len(self.documents)} documents, "
                f"total {len(existing_docs)} (may contain duplicates)"
            )
            return True

        except Exception as e:
            logger.error(f"Append-only flush failed: {e}")
            return False

    def _make_timestamp_name(self, prefix: str = "docs") -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"{prefix}_{ts}.json"

    def _atomic_write_json(self, final_path: str, data) -> None:
        tmp_path = final_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)



    def clear(self) -> None:
        """Clear the accumulated document list"""
        self.documents.clear()
        logger.info("Document buffer cleared")

    def delete_document(self, doc_id: int) -> bool:
        """Delete a document from the accumulated list"""
        try:
            original_len = len(self.documents)
            self.documents = [doc for doc in self.documents if doc["id"] != doc_id]

            if len(self.documents) < original_len:
                logger.info(f"Document {doc_id} removed from batch")
                return True
            else:
                logger.warning(f"Document {doc_id} not found in batch")
                return False
        except Exception as e:
            logger.error(f"Error removing document {doc_id} from batch: {e}")
            return False

    def is_available(self) -> bool:
        """Check if the output directory is writable"""
        import os

        return os.path.isdir(self.output_dir) and os.access(self.output_dir, os.W_OK)

    def get_document_count(self) -> int:
        """Get the current number of accumulated documents"""
        return len(self.documents)

    def dedup_file(self, file_path: str = None) -> bool:
        """
        Standalone deduplication: Remove duplicate documents from JSON file.
        Useful for periodic maintenance (e.g., daily cleanup).

        Args:
            file_path: Path to JSON file (default: self.output_file)

        Returns:
            True if successful
        """
        try:
            if file_path is None:
                file_path = os.path.join(self.output_dir, self.output_filename)

            if not os.path.exists(file_path):
                logger.warning(f"File does not exist: {file_path}")
                return False

            logger.info(f"Starting deduplication on {file_path}...")

            # Load all documents
            with open(file_path, "r", encoding="utf-8") as f:
                all_docs = json.load(f)

            original_count = len(all_docs)

            # Dedup by ID (keep last occurrence)
            doc_dict = {doc["id"]: doc for doc in all_docs}
            deduped_docs = sorted(doc_dict.values(), key=lambda x: x["id"])

            duplicate_count = original_count - len(deduped_docs)

            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(deduped_docs, f, ensure_ascii=False, indent=2)

            logger.info(
                f"Deduplication complete: Removed {duplicate_count} duplicates, {len(deduped_docs)} documents remaining"
            )
            return True

        except Exception as e:
            logger.error(f"Deduplication failed: {e}")
            return False

    def get_file_stats(self, file_path: str = None) -> Dict[str, any]:
        """
        Get statistics about the JSON file.

        Returns:
            Dict with: total_docs, file_size_mb, unique_ids, duplicate_count
        """
        try:
            if file_path is None:
                file_path = os.path.join(self.output_dir, self.output_filename)

            if not os.path.exists(file_path):
                return {"error": "File does not exist"}

            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

            with open(file_path, "r", encoding="utf-8") as f:
                all_docs = json.load(f)

            total_docs = len(all_docs)
            doc_ids = [doc["id"] for doc in all_docs]
            unique_ids = len(set(doc_ids))
            duplicate_count = total_docs - unique_ids

            return {
                "total_docs": total_docs,
                "unique_ids": unique_ids,
                "duplicate_count": duplicate_count,
                "file_size_mb": round(file_size_mb, 2),
                "has_duplicates": duplicate_count > 0,
            }

        except Exception as e:
            return {"error": str(e)}


def create_indexer(
    output_dir: str = "../indexer/input", output_filename: str = "docs.json", dedup_threshold_mb: int = 100
) -> FileBasedIndexer:
    """
    Create a FileBasedIndexer instance

    Args:
        output_dir: Output directory path (default "../indexer/input")
        output_filename: Output file name (default "docs.json")
        dedup_threshold_mb: File size threshold for dedup strategy (default 100MB)

    Returns:
        FileBasedIndexer instance
    Example:
        indexer = create_indexer("../indexer/input", "docs.json", dedup_threshold_mb=200)
    """
    return FileBasedIndexer(output_dir, output_filename, dedup_threshold_mb)
