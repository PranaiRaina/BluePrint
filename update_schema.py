import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("SUPABASE_DB_URL")

def update_schema():
    print("🔌 Connecting to DB...")
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            print("🛠️ Checking 'portfolios' table...")
            
            # Check if column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='portfolios' AND column_name='is_active';
            """)
            if cur.fetchone():
                print("✅ Column 'is_active' already exists.")
            else:
                print("➕ Adding 'is_active' column...")
                cur.execute("""
                    ALTER TABLE portfolios 
                    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT FALSE;
                """)
                conn.commit()
                print("✅ Schema updated successfully.")

if __name__ == "__main__":
    update_schema()
