"""
SQLite-based reports database for local development.
Replace with Supabase Postgres in production.
"""

import sqlite3
import os
import json
from datetime import date
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "reports.db")


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_reports_db():
    """Create the stock_reports table if it doesn't exist."""
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            report_date TEXT NOT NULL,
            market_report TEXT,
            news_report TEXT,
            fundamentals_report TEXT,
            sentiment_report TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, ticker, report_date)
        )
    """)
    conn.commit()
    conn.close()


def save_report(user_id: str, ticker: str, reports: dict, report_date: str = None):
    """Save or update a report for a given user/ticker/date."""
    if report_date is None:
        report_date = date.today().isoformat()

    conn = _get_connection()
    conn.execute("""
        INSERT INTO stock_reports (user_id, ticker, report_date, market_report, news_report, fundamentals_report, sentiment_report)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, ticker, report_date) DO UPDATE SET
            market_report = excluded.market_report,
            news_report = excluded.news_report,
            fundamentals_report = excluded.fundamentals_report,
            sentiment_report = excluded.sentiment_report,
            created_at = CURRENT_TIMESTAMP
    """, (
        user_id,
        ticker.upper(),
        report_date,
        reports.get("market_report", ""),
        reports.get("news_report", ""),
        reports.get("fundamentals_report", ""),
        reports.get("sentiment_report", ""),
    ))
    conn.commit()
    conn.close()


def get_report(user_id: str, ticker: str, report_date: str = None) -> dict | None:
    """Get a cached report for a given user/ticker/date. Returns None if not found."""
    if report_date is None:
        report_date = date.today().isoformat()

    conn = _get_connection()
    row = conn.execute("""
        SELECT * FROM stock_reports
        WHERE user_id = ? AND ticker = ? AND report_date = ?
    """, (user_id, ticker.upper(), report_date)).fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "ticker": row["ticker"],
        "report_date": row["report_date"],
        "market_report": row["market_report"],
        "news_report": row["news_report"],
        "fundamentals_report": row["fundamentals_report"],
        "sentiment_report": row["sentiment_report"],
        "created_at": row["created_at"],
    }


def get_all_reports_for_user(user_id: str) -> list[dict]:
    """Get all reports for a user, newest first."""
    conn = _get_connection()
    rows = conn.execute("""
        SELECT * FROM stock_reports
        WHERE user_id = ?
        ORDER BY report_date DESC, created_at DESC
    """, (user_id,)).fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "ticker": row["ticker"],
            "report_date": row["report_date"],
            "market_report": row["market_report"],
            "news_report": row["news_report"],
            "fundamentals_report": row["fundamentals_report"],
            "sentiment_report": row["sentiment_report"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def delete_report(user_id: str, ticker: str, report_date: str = None):
    """Delete a report for a given user/ticker/date."""
    if report_date is None:
        report_date = date.today().isoformat()

    conn = _get_connection()
    conn.execute("""
        DELETE FROM stock_reports
        WHERE user_id = ? AND ticker = ? AND report_date = ?
    """, (user_id, ticker.upper(), report_date))
    conn.commit()
    conn.close()


# Auto-init on import
init_reports_db()
