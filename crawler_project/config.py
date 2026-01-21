from dataclasses import dataclass
#集中管理参数
@dataclass(frozen=True)
class CrawlerConfig:
    user_agent: str = "TTDS-SearchEngine-Crawler (academic; contact: s2795693@deu.ac.uk)"
    timeout_seconds: int = 15
    max_items_per_feed: int = 20
    sleep_seconds: float = 1.0
    jitter_seconds: float = 0.5
    output_path: str = "output/articles.jsonl"
    min_text_length: int = 400

CONFIG = CrawlerConfig()
