## Workflow

```
                    ┌─────────────────┐
                    │   RSS Source    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   Crawler       │
                    │   Pipeline      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────────┐
                    │  ArticleRecord      │
                    │  {metadata+content} │
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │   Coordinator       │
                    └──┬────────────────┬─┘
                       │                │
           ┌───────────▼─────┐       ┌──▼──────────────┐
           │  Database       │       │    Indexer      │
           │  (metadata)     │       │  (doc_id+text)  │
           │  Returns doc_id │       │  Builds index   │
           └─────────────────┘       └─────────────────┘
```

A:
structure:
crawler_project/
README.md
requirements.txt
.env.example
main.py
config.py
sources/
**init**.py
feeds.yaml
crawler/
**init**.py
models.py
rss_parser.py
fetcher.py
extractor.py
pipeline.py
output.py
utils.py

config.py :Centralised configuration

crawler/models.py: Data model definitions

crawler/rss_parser.py (Step A):RSS feed parsing

crawler/fetcher.py (Step B):Robust HTML downloading

crawler/extractor.py (Step C):Main text extraction

crawler/utils.py:Shared utilities( Rate limiting with random jitter, Generating UTC timestamps)

crawler/pipeline.py:Core orchestration logic

crawler/output.py:Output abstraction

B:
Overall Architecture

The pipeline is intentionally designed in a layered and modular way:

RSS Feed
↓
[Step A] RSS Parser
↓
Article URLs + RSS metadata
↓
[Step B] HTML Fetcher
↓
Raw HTML
↓
[Step C] Content Extractor
↓
Structured Article Records
↓
JSONL Output (for inspection / further processing)

Each step is implemented as an independent module to make future extension (e.g. adding databases, new data sources, or parallelism) straightforward.
