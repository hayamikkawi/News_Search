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

## File Structure

```
crawler_project/
│
├── Configuration Files
│   ├── config.py                      # Centralized configuration management (Crawler, Database, Indexer)
│   ├── .env.example                   # Environment variable example (Database, Indexer)
│   ├── .env                           # Your configuration (not committed to Git)
│   └── requirements.txt               # Python dependencies
│
├── Core Modules
│   └── crawler/
│       ├── __init__.py
│       │
│       ├── models.py              # Data model definitions
│       │
│       ├── Crawler Components
│       │   ├── rss_parser.py          # RSS feed parsing
│       │   ├── fetcher.py             # HTML downloading
│       │   ├── extractor.py           # Content extraction
│       │   ├── pipeline.py            # Orchestration
│       │   └── utils.py               # Utility functions
│       │
│       ├── Database Modules
│       │   └── db_mysql.py                            # MySQL interaction
│       │       ├── save_article()                     # Save full article
│       │       ├── save_article_metadata_only()       # Save metadata only
│       │       ├── update_article_content()           # Update content
│       │       └── get_article_by_id()                # Query by ID
│       │
│       ├── Indexer Interface
│       │   └── indexer_interface.py    # Indexer communication interface
│       │       ├── IndexerInterface    # Abstract base class
│       │       ├── HTTPIndexer         # HTTP API implementation
│       │       ├── FileBasedIndexer    # File system implementation
│       │       └── DummyIndexer        # Test implementation
│       │
│       ├── Coordinator
│       │   └── coordinator.py           # Coordinate Crawler/DB/Indexer
│       │       ├── CrawlerCoordinator   # Coordinator class
│       │       ├── ProcessResult        # Processing result
│       │       └── create_coordinator() # Factory function
│       │
│       └── Output Modules
│           ├── output.py              # JSONL output (original)
│           └── output_mysql.py        # MySQL output (extension)
│
├── Executables
│   ├── main.py                        # Original main program (JSONL output)
│   ├── main_with_coordinator.py       # New: Integrated main program
│   ├── test_coordinator.py            # New: Test example
│   └── example_mysql_usage.py         # MySQL usage example
│
├── Documentation
│   └── README.md                      # Crawler description
│
└── Data Directory
    └── sources/                       # RSS source configuration
        ├── __init__.py
        └── feeds.yaml

```

## Data Flow Details

### Stage 1: Crawling Stage

```python
RSS Feed → RSS Parser → Article URLs
         → Fetcher → HTML
         → Extractor → ArticleRecord {
             metadata: {url, title, author, date, language}
             content: full_text
         }
```

### Stage 2: Storage and Indexing Stage (Core Design)

**Solution: Insert metadata first to get doc_id, then pass to indexer via JSON file**

```python
ArticleRecord
    │
    ▼
Coordinator.process_article():
    │
    ├─► Step 1: database.save_article_metadata_only(article)
    │           INSERT INTO articles (url, title, author, ..., text_content)
    │           VALUES (..., ..., ..., NULL)  -- content is NULL
    │           RETURNING id  -- get the auto-generated doc_id
    │
    │           Results: returns doc_id = 12345
    │
    ├─► Step 2: indexer.send_document(doc_id=12345, content=text, metadata={...})
    │           Accumulate to memory in Indexer format:
    │           {
    │               "id": 12345,
    │               "title": "Article Title",
    │               "description": "Article summary...",
    │               "content": "full article text..."
    │           }
    │
    │           Results: Document added to batch
    │
    ├─► Step 2.5: indexer.flush() (after batch processing)
    │           Write all documents to ../indexer/input/docs.json:
    │           [
    │               {"id": 12345, "title": "...", "description": "...", "content": "..."},
    │               {"id": 12346, "title": "...", "description": "...", "content": "..."}
    │           ]
    │
    │           Results: Indexer can read JSON file and build inverted index
    │
    └─► Step 3 (optional): database.update_article_content(doc_id, text)
                UPDATE articles SET text_content = ? WHERE id = 12345

                Results: If you want to store full text in the database as well
```
