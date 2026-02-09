# TODO List for Crawler Project

### Next Step

1. ONGOING Dockerize as a service => Crawler running as a long-lived service [](#dockerize)
2. PENDING Scheduled polling => Periodically fetch from RSS sources (e.g., once every hour, 100 docs) [](#scheduled-polling)
3. ONGOING Incremental updates => Only process new articles to avoid duplication [](#incremental-updates)
4. DONE Database persistence => MySQL state retention
5. ONGOING JSON append mode => append new documents to the indexer's docs.json instead of overwriting [](#json-append-mode)
6. TODO Fix gaps in auto-increment IDs => Solution: check URL existence in DB before inserting new record [](#fix-gaps-in-auto-increment-ids)

## New Architecture Overview

```
┌────────────────────────────────────────┐
│         Docker Container               │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │   Scheduler (APScheduler)        │  │
│  │   - Every 1 hour trigger         │  │
│  └──────────┬───────────────────────┘  │
│             │                          │
│             ▼                          │
│  ┌──────────────────────────────────┐  │
│  │   Crawler Service                │  │
│  │   1. Fetch RSS feeds             │  │
│  │   2. Check for new articles      │  │
│  │   3. Extract content             │  │
│  └──────────┬───────────────────────┘  │
│             │                          │
│             ▼                          │
│  ┌──────────────────────────────────┐  │
│  │   Coordinator                    │  │
│  │   - Check duplicates (DB)        │  │
│  │   - Save metadata → doc_id       │  │
│  │   - Append to JSON               │  │
│  └──┬───────────────────────┬───────┘  │
│     │                       │          │
└─────┼───────────────────────┼──────────┘
      │                       │
      │ MySQL Connection      │ Volume Mount
      ▼                       ▼
┌──────────────┐    ┌──────────────────┐
│   MySQL      │    │  Shared Volume   │
│   Container  │    │  ../indexer/     │
│   (Separate) │    │    input/        │
└──────────────┘    │  docs.json       │
                    └──────────────────┘
```

## Core Features to Implement

TODO

## Dockerize

### TODO

1. Create `dockerfile` for Crawler service
2. Create `docker-compose.yml` to define services:
   - MySQL database
   - Crawler service
   - Indexer service (for volume sharing)
   - Configure volumes for data persistence
3. Test containerized setup

### docker-compose.yaml

```yaml
version: "3.8"

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: ttds_search_engine
      MYSQL_USER: ttds_app
      MYSQL_PASSWORD: ttds#123
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 3

  crawler:
    build: ./crawler_project
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      MYSQL_HOST: mysql
      MYSQL_PORT: 3306
      MYSQL_USER: ttds_app
      MYSQL_PASSWORD: ttds#123
      MYSQL_DATABASE: ttds_search_engine
      INDEXER_OUTPUT_DIR: /shared/indexer/input
      INDEXER_OUTPUT_FILENAME: docs.json
    volumes:
      - indexer_data:/shared/indexer/input
      - ./logs:/app/logs
    restart: unless-stopped

  indexer:
    # Indexer 服务配置
    volumes:
      - indexer_data:/app/input

volumes:
  mysql_data:
  indexer_data:
```

### Docker file

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Crawler Code
COPY crawler_project/ .

# Set Environment vars
ENV PYTHONUNBUFFERED=1

# Run ASPScheduler
CMD ["python", "scheduler.py"]
```

## Incremental updates

**Problems**

- Currently, the crawler processes all articles from the RSS feeds every time it runs, leading to duplication in the indexer and wasted resources.
- Need to track which articles have already been processed.

**Solutions**

1. **Database Tracking**: Use the existing MySQL database to track processed articles by storing their URLs or unique identifiers.
2. **Coordinator Check**: Before processing an article, the coordinator checks the database to see if it has already been processed.
3. **Skip Duplicates**: If an article is found in the database, skip processing it.
4. **Logging**: Log skipped articles for auditing purposes.

## JSON Append Mode

**Problems**

- The current implementation overwrites the `docs.json` file each time new documents are sent to the indexer, leading to loss of previously indexed documents.
- Need to append new documents instead of overwriting.

**Solutions A**

1. **Load Existing Data**: When initializing the `IndexerInterface`, check if `docs.json` exists. If it does, load the existing documents into memory.
2. **Append New Documents**: When `send_document` is called, append the new document to the in-memory list.
3. **Flush to Disk**: When `flush` is called, write the entire list (existing + new) back to `docs.json`.
4. **Concurrency Handling**: Implement file locking to prevent concurrent write issues if multiple processes might access the file simultaneously.

**Solutions B (Alternative)**

```python
# 1. Every time generate a timestamped file instead of overwriting
from datetime import datetime
filename = f"docs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
# 2. Indexer reads all JSON files in the directory and merges them
```

1. **Timestamped Files**: Instead of appending to a single `docs.json`, create a new file with a timestamp each time documents are flushed (e.g., `docs_20231010_101530.json`).
2. **Indexer Aggregation**: Modify the indexer to read all JSON files in the input directory and aggregate them during indexing.

## Scheduled Polling

**Problems**

- The crawler currently runs only when manually triggered, which is not ideal for keeping the index up-to-date.
- Need to automate the crawling process to run at regular intervals.

**Solutions A**

1. **Use APScheduler**: Integrate the APScheduler library to schedule periodic tasks within the crawler service.
2. **Define Job**: Create a job that runs the crawling process (fetching RSS feeds, processing articles) at defined intervals (e.g., every hour??????????).
3. **Docker Integration**: Ensure the scheduled job runs within the Docker container as part of the main process.
4. **Logging and Monitoring**: Implement logging for each scheduled run to monitor success/failure and performance.
5. **Configuration**: Allow configuration of the polling interval via environment variables or configuration files.
6. **Graceful Shutdown**: Ensure that the scheduler can be gracefully shut down when the Docker container stops.

**Solutions B (Cancelled)**

_This solution is less efficient due to container restart overhead, because it requires restarting the entire Docker container to trigger the crawler._

1. **Cron Jobs**: Use cron jobs within the Docker container to trigger the crawler script at regular intervals.
2. **External Scheduler**: Use an external scheduling service (e.g., Kubernetes CronJobs, AWS Lambda with CloudWatch Events) to trigger the crawler at set intervals.

## Fix Gaps in Auto-Increment IDs

**Problems**

```
mysql> select id from articles order by id;
+----+
| id |
+----+
|  1 |
|  2 |
|  3 |
|  4 |
|  5 |
|  6 |
|  7 |
|  8 |
|  9 |
| 10 |
| 11 |
| 12 |
| 13 |
| 14 |
| 15 |
| 16 |
| 17 |
| 18 |
| 19 |
| 20 |
| 29 |
| 62 |
| 64 |
| 67 |
| 69 |
+----+
25 rows in set (0.00 sec)
```

- When inserting new articles, gaps appear in the auto-increment IDs due to skipped inserts (e.g., duplicate URLs).

**Root Cause**

This is because MySQL's `insert ... ON DUPLICATE KEY UPDATE` statements still consume an auto-increment ID even when the insert fails due to a duplicate key constraint (e.g., `idx_url_unique` on the URL field).

Procedure:

- First insertion: Insert new articles, id = 1, 2, 3, ... (no gaps)
- Second insertion
  - Attempt to insert an article with URL that already exists (e.g., URL of id=20)
  - Constraint `UNIQUE KEY idx_url_unique (url, feed_url)` triggers
  - `ON DUPLICATE KEY UPDATE` clause runs, but the auto-increment ID is still consumed
  - MySQL will first try to insert with id=21, but fails due to duplicate URL, so it executes the `UPDATE` instead of `INSERT`
  - But id=21 is already consumed, so the next successful insert gets id=22, leading to gaps
- Subsequent insertions continue this pattern, leading to more gaps

**Solutions**

1. **Pre-Check Existence**: Before attempting to insert a new article, perform a `SELECT` query to check if the URL already exists in the database. Only proceed with the `INSERT` if it does not exist. => Implements the pre-check logic in `save_article_metadata_only` of `db_mysql.py`: check if URL exists first, if not, then insert; else update, avoiding consumption of auto-increment ID.

[](#next-step)
