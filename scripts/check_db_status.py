import os, psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
load_dotenv()
try:
    with psycopg.connect(os.getenv("SUPABASE_DB_URL"), row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT count(*) as count FROM chat_history")
            res = cursor.fetchone()
            print(f"Total messages in DATABASE: {res['count']}")
            
            cursor.execute("SELECT session_id, title, user_id FROM chat_sessions ORDER BY updated_at DESC LIMIT 10")
            rows = cursor.fetchall()
            print("\nRecent sessions in DATABASE:")
            for r in rows:
                cursor.execute("SELECT count(*) as count FROM chat_history WHERE session_id = %s", (r["session_id"],))
                msg_count = cursor.fetchone()["count"]
                print(f" - {r['session_id']} | Title: {r['title']} | User: {r['user_id']} | Messages: {msg_count}")
except Exception as e:
    print(f"Error checking DB: {e}")
