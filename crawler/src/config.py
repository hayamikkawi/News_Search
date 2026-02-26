from dataclasses import dataclass
import os


# Centralized configuration management
@dataclass(frozen=True)
class CrawlerConfig:
    user_agent: str = os.getenv(
        "CRAWLER_USER_AGENT", "TTDS-SearchEngine-Crawler (academic; contact: s2795693@deu.ac.uk)"
    )
    timeout_seconds: int = int(os.getenv("CRAWLER_TIMEOUT_SECONDS", "15"))
    max_items_per_feed: int = int(os.getenv("MAX_ITEMS_PER_FEED", "20"))
    sleep_seconds: float = float(os.getenv("CRAWLER_SLEEP_SECONDS", "1.0"))
    jitter_seconds: float = float(os.getenv("CRAWLER_JITTER_SECONDS", "0.5"))
    output_path: str = os.getenv("CRAWLER_OUTPUT_PATH", "output/articles.jsonl")
    min_text_length: int = int(os.getenv("MIN_TEXT_LENGTH", "400"))


@dataclass(frozen=True)
class MySQLConfig:
    """MySQL Database Configuration"""

    host: str = os.getenv("MYSQL_HOST", "localhost")
    port: int = int(os.getenv("MYSQL_PORT", "3306"))
    user: str = os.getenv("MYSQL_USER", "ttds_app")
    password: str = os.getenv("MYSQL_PASSWORD", "ttds#123")
    database: str = os.getenv("MYSQL_DATABASE", "ttds_search_engine")
    pool_size: int = int(os.getenv("MYSQL_POOL_SIZE", "5"))


@dataclass(frozen=True)
class IndexerConfig:
    """Indexer Configuration"""

    # Output directory for Indexer input
    output_dir: str = os.getenv("INDEXER_OUTPUT_DIR", "../indexer/input")
    # Output filename for Indexer
    output_filename: str = os.getenv("INDEXER_OUTPUT_FILENAME", "docs.json")
    # Whether to save content to the database (enabled by default)
    save_content_to_db: bool = os.getenv("SAVE_CONTENT_TO_DB", "true").lower() == "true"
    # JSON flush mode: "append" (merge with dedup), "overwrite" (replace), "append_only" (fast, no dedup)
    flush_mode: str = os.getenv("INDEXER_FLUSH_MODE", "new_file")
    # File size threshold (MB) for choosing dedup strategy
    dedup_threshold_mb: int = int(os.getenv("INDEXER_DEDUP_THRESHOLD_MB", "100"))


CONFIG = CrawlerConfig()
MYSQL_CONFIG = MySQLConfig()
INDEXER_CONFIG = IndexerConfig()
