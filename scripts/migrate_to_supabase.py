import sqlite3
import psycopg
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# CONFIG
SQLITE_DB_PATH = os.getenv("DB_PATH", "chat_history.db")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
# Optional: Override all migrated chats to a single Supabase User ID
MIGRATE_TO_USER_ID = os.getenv("SUPABASE_MIGRATE_USER_ID")

def migrate():
    if not SUPABASE_DB_URL:
        print("Error: SUPABASE_DB_URL not found in .env")
        return

    print(f"Connecting to SQLite: {SQLITE_DB_PATH}")
    sq_conn = sqlite3.connect(SQLITE_DB_PATH)
    sq_conn.row_factory = sqlite3.Row
    sq_cursor = sq_conn.cursor()

    print(f"Connecting to Supabase Postgres...")
    try:
        # Connect with autocommit for clean migration
        pg_conn = psycopg.connect(SUPABASE_DB_URL, autocommit=True)
    except Exception as e:
        print(f"Failed to connect to Supabase: {e}")
        return
    
    try:
        # 1. Fetch all SQLite data
        print("Reading SQLite data...")
        sq_cursor.execute("SELECT * FROM chat_sessions")
        sessions = [dict(row) for row in sq_cursor.fetchall()]
        
        sq_cursor.execute("SELECT * FROM chat_history")
        messages = [dict(row) for row in sq_cursor.fetchall()]
        
        print(f"Loaded {len(sessions)} sessions and {len(messages)} messages from SQLite.")

        with pg_conn.cursor() as pg_cursor:
            # 2. Migrate chat_sessions first (Foreign Key requirement)
            print("Migrating chat_sessions...")
            for session in sessions:
                user_id = MIGRATE_TO_USER_ID if MIGRATE_TO_USER_ID else session["user_id"]
                
                # Format metadata
                metadata = session.get("metadata")
                metadata_json = None
                if metadata:
                    try:
                        metadata_json = json.dumps(json.loads(metadata))
                    except:
                        metadata_json = json.dumps({"raw": metadata})

                pg_cursor.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_id, title, metadata, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    (session["session_id"], user_id, session["title"], metadata_json, session["created_at"], session["updated_at"])
                )

            # 3. Handle orphaned sessions (Messages with IDs not in sessions table)
            print("Checking for orphaned messages...")
            existing_session_ids = {s["session_id"] for s in sessions}
            orphaned_session_ids = {m["session_id"] for m in messages if m["session_id"] not in existing_session_ids}
            
            if orphaned_session_ids:
                print(f"Found {len(orphaned_session_ids)} orphaned sessions. Creating them now...")
                for sess_id in orphaned_session_ids:
                    user_id = MIGRATE_TO_USER_ID if MIGRATE_TO_USER_ID else "ff5b4fce-3523-44de-bc9e-0bf8a390fc3c" # Fallback if unknown
                    pg_cursor.execute(
                        """
                        INSERT INTO chat_sessions (session_id, user_id, title)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (session_id) DO NOTHING
                        """,
                        (sess_id, user_id, "Imported Conversation")
                    )

            # 4. Migrate chat_history
            print("Migrating chat_history...")
            for msg in messages:
                user_id = MIGRATE_TO_USER_ID if MIGRATE_TO_USER_ID else msg["user_id"]
                
                pg_cursor.execute(
                    """
                    INSERT INTO chat_history (user_id, session_id, role, content, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, msg["session_id"], msg["role"], msg["content"], msg["timestamp"])
                )
        
        print("✅ Migration complete!")

    except Exception as e:
        print(f"❌ Error during migration: {e}")
    finally:
        sq_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    migrate()
