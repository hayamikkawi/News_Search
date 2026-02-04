from dataclasses import dataclass
import os


# Centralized configuration management
@dataclass(frozen=True)
class CrawlerConfig:
    user_agent: str = (
        "TTDS-SearchEngine-Crawler (academic; contact: s2795693@deu.ac.uk)"
    )
    timeout_seconds: int = 15
    max_items_per_feed: int = 20
    sleep_seconds: float = 1.0
    jitter_seconds: float = 0.5
    output_path: str = "output/articles.jsonl"
    min_text_length: int = 400


@dataclass(frozen=True)
class MySQLConfig:
    """MySQL Database Configuration"""

    host: str = os.getenv("MYSQL_HOST", "localhost")
    port: int = int(os.getenv("MYSQL_PORT", "3306"))
    user: str = os.getenv("MYSQL_USER", "root")
    password: str = os.getenv("MYSQL_PASSWORD", "")
    database: str = os.getenv("MYSQL_DATABASE", "crawler_db")
    pool_size: int = int(os.getenv("MYSQL_POOL_SIZE", "5"))


@dataclass(frozen=True)
class IndexerConfig:
    """Indexer Configuration"""

    # Indexer Type: "http", "file", "dummy"
    type: str = os.getenv("INDEXER_TYPE", "http")
    # Base URL for HTTP Indexer
    base_url: str = os.getenv("INDEXER_BASE_URL", "http://localhost:8080")
    # HTTP timeout (seconds)
    timeout: int = int(os.getenv("INDEXER_TIMEOUT", "30"))
    # Output directory for file-based Indexer
    output_dir: str = os.getenv("INDEXER_OUTPUT_DIR", "./indexer_input")
    # Whether to save content to the database (False saves only metadata to save space)
    save_content_to_db: bool = (
        os.getenv("SAVE_CONTENT_TO_DB", "false").lower() == "true"
    )


CONFIG = CrawlerConfig()
MYSQL_CONFIG = MySQLConfig()
INDEXER_CONFIG = IndexerConfig()
