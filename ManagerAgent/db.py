import os
from contextlib import contextmanager
from fastapi import HTTPException
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

pool = None

def init_db_pool():
    global pool
    if SUPABASE_DB_URL:
        print("Initializing Supabase Postgres Connection Pool...")
        pool = ConnectionPool(
            conninfo=SUPABASE_DB_URL,
            max_size=20,
            kwargs={
                "autocommit": True,
                "row_factory": dict_row,
                "prepare_threshold": None,  # Disable prepared statements for PGBouncer
            },
        )
    else:
        print("WARNING: SUPABASE_DB_URL not found in .env. Database operations will fail.")

@contextmanager
def get_db():
    """Context manager for getting a connection from the pool."""
    if not pool:
        # Try to init if not done (e.g. if imported first time)
        init_db_pool()
        if not pool:
            raise HTTPException(status_code=500, detail="Database pool not initialized.")
    
    with pool.connection() as conn:
        yield conn
