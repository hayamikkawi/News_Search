import json
import os
from typing import Iterable
from .models import ArticleRecord
#先 JSONL，后续可接 SQL
def write_jsonl(path: str, records: Iterable[ArticleRecord]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.__dict__, ensure_ascii=False) + "\n")
