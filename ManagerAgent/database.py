
import os
from contextlib import contextmanager
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

# --- Database Setup (Supabase Postgres) ---
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

# Initialize Connection Pool
pool = None

def init_pool():
    global pool
    if SUPABASE_DB_URL and pool is None:
        print("Initializing Supabase Postgres Connection Pool...")
        pool = ConnectionPool(
            conninfo=SUPABASE_DB_URL,
            # Opening a connection to the Supabase pooler measures ~1.9s, so keep
            # a few warm. min_size=1 meant every concurrent request paid for one.
            min_size=5,
            max_size=20,
            kwargs={
                # Without this every request pays BEGIN + query + COMMIT = 3 network
                # round trips (~840ms) instead of 1 (~280ms). Callers that need
                # several statements to be atomic use `with conn.transaction():`.
                "autocommit": True,
                "row_factory": dict_row,
                "prepare_threshold": None,  # Disable prepared statements for PGBouncer (Transaction Pooling)
            },
        )
    elif not SUPABASE_DB_URL:
        print("WARNING: SUPABASE_DB_URL not found in .env. Database operations will fail.")

def pool_wait(timeout: float = 20.0):
    """Block until min_size connections are established (call once at startup)."""
    if pool is not None:
        pool.wait(timeout=timeout)


@contextmanager
def get_db():
    """Context manager for getting a connection from the pool."""
    if pool is None:
        init_pool()
    
    if pool is None:
        raise Exception("Database pool not initialized. Check SUPABASE_DB_URL.")
        
    with pool.connection() as conn:
        yield conn

def init_db():
    """No-op for migration to Supabase (Schema assumed created via SQL Editor)."""
    pass
