from typing import Any, Dict, List, Optional
import mysql.connector
import os
from datetime import datetime

class DocStore:

    def __init__(self):
        self._conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
        )
    
    def fetch_docs_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join(["%s"] * len(ids))
        sql = f"""
            SELECT
              id,
              COALESCE(title, rss_title) AS headline,
              COALESCE(rss_published_at, fetched_at) AS time,
              COALESCE(final_url, url) AS url
            FROM articles
            WHERE id IN ({placeholders})
        """
        cur = self._conn.cursor(dictionary=True)
        cur.execute(sql, ids)
        rows = cur.fetchall()
        cur.close()
        return rows

    def fetch_latest(self, limit: int) -> List[Dict[str, Any]]:
        sql = """
            SELECT
              id,
              COALESCE(title, rss_title) AS headline,
              COALESCE(rss_published_at, fetched_at) AS time,
              COALESCE(final_url, url) AS url
            FROM articles
            ORDER BY COALESCE(rss_published_at, fetched_at) DESC
            LIMIT %s
        """
        cur = self._conn.cursor(dictionary=True)
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
        cur.close()
        return rows

    def fetch_candidate_ids_by_time(
        self, time_from: Optional[datetime], time_to: Optional[datetime]
    ) -> Optional[set[str]]:
        if not time_from and not time_to: 
            return None
        if time_from and time_to: 
            sql = """
                SELECT id FROM articles
                WHERE COALESCE(rss_published_at, fetched_at) BETWEEN %s AND %s
            """
            params = (time_from, time_to)
        elif time_from:
            sql = """
                SELECT id FROM articles
                WHERE COALESCE(rss_published_at, fetched_at) >= %s
            """
            params = (time_from,)
        else: 
            sql = """
                SELECT id FROM articles
                WHERE COALESCE(rss_published_at, fetched_at) <= %s
            """
            params = (time_to,)
        cur = self._conn.cursor()
        cur.execute(sql, params)
        ids = {row[0] for row in cur.fetchall()}
        cur.close()
        return ids