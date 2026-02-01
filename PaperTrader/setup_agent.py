from pathlib import Path
from dotenv import load_dotenv
import os

# Load Env FIRST
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from ManagerAgent.db import init_db_pool, get_db

def setup_agent_user():
    init_db_pool()
    agent_uuid = "00000000-0000-0000-0000-000000000000"
    
    with get_db() as conn:
        with conn.cursor() as cur:
            # DEBUG: List tables
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            print(f"DEBUG: Found tables: {[row['table_name'] for row in cur.fetchall()]}")

            # Check if exists in AUTH schema
            cur.execute("SELECT id FROM auth.users WHERE id = %s", (agent_uuid,))
            if cur.fetchone():
                print("✅ Agent User already exists.")
            else:
                print("creating Agent User in auth.users...")
                # Insert into auth.users (Requires Service Role / Postgres Admin)
                cur.execute(
                    """
                    INSERT INTO auth.users (id, email, raw_user_meta_data, aud, role) 
                    VALUES (%s, %s, %s, 'authenticated', 'authenticated')
                    """,
                    (agent_uuid, "agent@rosehacks.ai", '{"full_name": "The Wolf (AI Agent)"}')
                )
                print("✅ Agent User Created.")

if __name__ == "__main__":
    setup_agent_user()
