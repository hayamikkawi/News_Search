import logging
from typing import Any, Dict, List, Optional
import mysql.connector
import os
from datetime import datetime
from mysql.connector import Error

class DocStore:
    def __init__(self):
        self._conn = None
        self._connect()

    def _connect(self):
        self._conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
            autocommit=True,
        )

    def _ensure_conn(self):
        try:
            # reconnect=True will re-open if dropped
            self._conn.ping(reconnect=True, attempts=3, delay=2)
        except Error:
            # if the connection object is too broken, fully recreate it
            try:
                self._conn.close()
            except Exception:
                pass
            self._connect()

    def cursor(self):
        self._ensure_conn()
        return self._conn.cursor(dictionary=True)

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
        cur = self.cursor()
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
        cur = self.cursor()
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
        cur = self.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        logging.info("rows example:", rows[:5], "type:", type(rows[0]) if rows else None)
        ids = {row["id"] for row in rows}
        cur.close()
        return ids