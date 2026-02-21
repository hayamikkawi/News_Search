import time
import random
from datetime import datetime

# Utility functions for rate limiting and time handling


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def polite_sleep(base_seconds: float, jitter_seconds: float) -> None:
    time.sleep(base_seconds + random.random() * jitter_seconds)
