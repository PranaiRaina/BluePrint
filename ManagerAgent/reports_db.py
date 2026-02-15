"""
Supabase Postgres-backed reports database.
Uses the shared psycopg connection pool from ManagerAgent.database.
"""

from datetime import date
from ManagerAgent.database import get_db


def save_report(user_id: str, ticker: str, reports: dict, report_date: str = None):
    """Save or update a report for a given user/ticker/date."""
    if report_date is None:
        report_date = date.today().isoformat()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO stock_reports (user_id, ticker, report_date, market_report, news_report, fundamentals_report, sentiment_report)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(user_id, ticker, report_date) DO UPDATE SET
                    market_report = EXCLUDED.market_report,
                    news_report = EXCLUDED.news_report,
                    fundamentals_report = EXCLUDED.fundamentals_report,
                    sentiment_report = EXCLUDED.sentiment_report,
                    created_at = now()
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


def get_report(user_id: str, ticker: str, report_date: str = None) -> dict | None:
    """Get a cached report for a given user/ticker/date. Returns None if not found."""
    if report_date is None:
        report_date = date.today().isoformat()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, ticker, report_date, market_report, news_report,
                       fundamentals_report, sentiment_report, created_at
                FROM stock_reports
                WHERE user_id = %s AND ticker = %s AND report_date = %s
            """, (user_id, ticker.upper(), report_date))
            row = cur.fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "user_id": str(row["user_id"]),
        "ticker": row["ticker"],
        "report_date": str(row["report_date"]),
        "market_report": row["market_report"],
        "news_report": row["news_report"],
        "fundamentals_report": row["fundamentals_report"],
        "sentiment_report": row["sentiment_report"],
        "created_at": str(row["created_at"]),
    }


def get_all_reports_for_user(user_id: str) -> list[dict]:
    """Get all reports for a user, newest first."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, ticker, report_date, market_report, news_report,
                       fundamentals_report, sentiment_report, created_at
                FROM stock_reports
                WHERE user_id = %s
                ORDER BY report_date DESC, created_at DESC
            """, (user_id,))
            rows = cur.fetchall()

    return [
        {
            "id": row["id"],
            "user_id": str(row["user_id"]),
            "ticker": row["ticker"],
            "report_date": str(row["report_date"]),
            "market_report": row["market_report"],
            "news_report": row["news_report"],
            "fundamentals_report": row["fundamentals_report"],
            "sentiment_report": row["sentiment_report"],
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def delete_report(user_id: str, ticker: str, report_date: str = None):
    """Delete a report for a given user/ticker/date."""
    if report_date is None:
        report_date = date.today().isoformat()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM stock_reports
                WHERE user_id = %s AND ticker = %s AND report_date = %s
            """, (user_id, ticker.upper(), report_date))
        conn.commit()
