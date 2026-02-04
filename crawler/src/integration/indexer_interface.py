"""
Indexer Interface Module
File-based implementation to communicate with the Indexer component
Generates JSON array format files as required by the Indexer
"""

import logging
import json

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

    def __init__(self, output_dir: str, output_filename: str = "docs.json"):
        """
        Initialize the file-based Indexer

        Args:
            output_dir: Output directory path
            output_filename: Output file name (default "docs.json")
        """
        import os

        self.output_dir = output_dir
        self.output_filename = output_filename
        self.documents = []  # Accumulated document list
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

    def flush(self) -> bool:
        """
        Write all accumulated documents to a JSON file

        Returns:
            True if successful, False otherwise
        """
        try:
            import os

            if not self.documents:
                logger.warning("No documents to flush")
                return True

            file_path = os.path.join(self.output_dir, self.output_filename)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)

            logger.info(f"Flushed {len(self.documents)} documents to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error flushing documents to file: {e}")
            return False

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


def create_indexer(output_dir: str = "../indexer/input", output_filename: str = "docs.json") -> FileBasedIndexer:
    """
    Create a FileBasedIndexer instance

    Args:
        output_dir: Output directory path (default "../indexer/input")
        output_filename: Output file name (default "docs.json")

    Returns:
        FileBasedIndexer instance
    Example:
        indexer = create_indexer("../indexer/input", "docs.json")
    """
    return FileBasedIndexer(output_dir, output_filename)
