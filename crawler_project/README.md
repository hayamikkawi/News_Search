## Workflow

```
┌─────────────┐
│  RSS Feed   │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────┐
│  Crawler Pipeline                │
│  - Fetch HTML                    │
│  - Extract content               │
└──────┬───────────────────────────┘
       │ ArticleRecord
       ▼
┌──────────────────────────────────┐
│  Coordinator                     │
│  1. Save metadata → DB (doc_id)  │
│  2. Send to FileBasedIndexer     │
└──┬──────────────────────────┬────┘
   │                          │
   ▼                          ▼
┌─────────┐          ┌────────────────────┐
│Database │          │FileBasedIndexer    │
│(MySQL)  │          │ - Accumulate docs  │
│         │          │ - Convert format   │
│doc_id=1 │          │   {id, title,      │
│doc_id=2 │          │    description,    │
│doc_id=3 │          │    content}        │
└─────────┘          │ - Flush to JSON    │
                     └──────────┬─────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ ../indexer/input/   │
                     │    docs.json        │
                     │ [                   │
                     │   {id:1, ...},      │
                     │   {id:2, ...},      │
                     │   {id:3, ...}       │
                     │ ]                   │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Indexer            │
                     │  (indexer.py)       │
                     │  - Read JSON        │
                     │  - Preprocess       │
                     │  - Build index      │
                     └─────────────────────┘
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

## Core Interface Details

### 1. db_mysql.py - database interface

```python
def save_article_metadata_only(article: ArticleRecord) -> Optional[int]:
    """Only save metadata, return doc_id"""

def update_article_content(doc_id: int, text_content: str) -> bool:
    """Update full article content"""

def get_article_by_id(doc_id: int) -> Optional[Dict]:
    """Query article by doc_id"""
```

### 2. indexer_interface.py - Indexer interface

```python
class FileBasedIndexer:
    def __init__(output_dir, output_filename="docs.json")

    def send_document(doc_id, content, metadata) -> bool
        """Accumulate documents in memory, convert to Indexer format"""

    def flush() -> bool
        """Write all documents to JSON file"""

    def clear() -> None
        """Clear document cache"""

    def delete_document(doc_id) -> bool
        """Delete document from cache"""

    def is_available() -> bool
        """Check if output directory is writable"""

    def get_document_count() -> int
        """Get the current number of accumulated documents"""
```

**Factory function**：

```python
def create_indexer(output_dir="../indexer/input",
                   output_filename="docs.json") -> FileBasedIndexer
```

### 3. coordinator.py - Coordinator

```python
class CrawlerCoordinator:
    def __init__(database, indexer, save_content_to_db=False)

    def process_article(article: ArticleRecord) -> ProcessResult:
        """Process a single article
        1. Save metadata to DB → doc_id
        2. Send (doc_id, content) to Indexer
        3. Optional: Save content to DB
        """

    def process_articles_batch(articles) -> List[ProcessResult]:
        """Process articles in batch"""
```
