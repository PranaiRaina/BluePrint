"""
Supabase Postgres-backed holdings database.
Uses the shared psycopg connection pool from ManagerAgent.database.
Provides per-user holdings isolation via user_id scoping + RLS.
"""

from datetime import datetime
from ManagerAgent.database import get_db


def get_holdings(user_id: str, status: str = None) -> list[dict]:
    """
    Get all holdings for a user, optionally filtered by status.
    status: 'pending', 'verified', or None (all).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute("""
                    SELECT id, user_id, ticker, asset_name, quantity, price,
                           source_doc, status, created_at, updated_at
                    FROM holdings
                    WHERE user_id = %s AND status = %s
                    ORDER BY created_at DESC
                """, (user_id, status))
            else:
                cur.execute("""
                    SELECT id, user_id, ticker, asset_name, quantity, price,
                           source_doc, status, created_at, updated_at
                    FROM holdings
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                """, (user_id,))
            rows = cur.fetchall()

    return [_row_to_dict(row) for row in rows]


def get_holding(user_id: str, ticker: str) -> dict | None:
    """Get a single holding for a user by ticker."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, ticker, asset_name, quantity, price,
                       source_doc, status, created_at, updated_at
                FROM holdings
                WHERE user_id = %s AND ticker = %s
            """, (user_id, ticker.upper()))
            row = cur.fetchone()

    if row is None:
        return None
    return _row_to_dict(row)


def upsert_holding(user_id: str, holding: dict) -> dict:
    """
    Insert or update a holding. Uses ON CONFLICT(user_id, ticker) to upsert.
    Returns the upserted row.
    """
    ticker = (holding.get("ticker") or "").upper()
    asset_name = holding.get("asset_name", "")
    quantity = float(holding.get("quantity", 0))
    price = float(holding.get("price", 0))
    source_doc = holding.get("source_doc", "Manual Entry")
    status = holding.get("status", "verified")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO holdings (user_id, ticker, asset_name, quantity, price, source_doc, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(user_id, ticker) DO UPDATE SET
                    asset_name = EXCLUDED.asset_name,
                    quantity = EXCLUDED.quantity,
                    price = EXCLUDED.price,
                    source_doc = EXCLUDED.source_doc,
                    status = EXCLUDED.status
                RETURNING id, user_id, ticker, asset_name, quantity, price,
                          source_doc, status, created_at, updated_at
            """, (user_id, ticker, asset_name, quantity, price, source_doc, status))
            row = cur.fetchone()
        conn.commit()

    return _row_to_dict(row)


def update_holding_status(user_id: str, holding_id: str, new_status: str) -> bool:
    """Update the status of a holding (e.g. pending → verified). Returns True if found."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE holdings
                SET status = %s
                WHERE id = %s AND user_id = %s
            """, (new_status, holding_id, user_id))
            updated = cur.rowcount > 0
        conn.commit()

    return updated


def delete_holding(user_id: str, ticker: str) -> int:
    """Delete all holdings for a given user + ticker. Returns number of rows deleted."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM holdings
                WHERE user_id = %s AND ticker = %s
            """, (user_id, ticker.upper()))
            deleted = cur.rowcount
        conn.commit()

    return deleted


def _row_to_dict(row: dict) -> dict:
    """Convert a database row to a JSON-serializable dict."""
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "ticker": row["ticker"],
        "asset_name": row["asset_name"],
        "quantity": float(row["quantity"]),
        "price": float(row["price"]),
        "source_doc": row["source_doc"],
        "status": row["status"],
        "timestamp": str(row["created_at"]),  # Keep 'timestamp' key for frontend compat
    }
