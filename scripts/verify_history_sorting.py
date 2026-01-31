import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("SUPABASE_DB_URL")

def verify_sorting():
    user_id = "00000000-0000-0000-0000-000000000000"
    session_id = "11111111-1111-1111-1111-111111111111"
    
    print(f"Connecting to database...")
    with psycopg.connect(DB_URL, row_factory=dict_row, prepare_threshold=None) as conn:
        with conn.cursor() as cursor:
            # 1. Clean up
            cursor.execute("DELETE FROM chat_history WHERE session_id = %s", (session_id,))
            cursor.execute("DELETE FROM chat_sessions WHERE session_id = %s", (session_id,))
            
            # 2. Insert rapid pairs
            print("Inserting 5 rapid message pairs...")
            for i in range(5):
                # Ensure session exists
                cursor.execute("""
                    INSERT INTO chat_sessions (session_id, user_id, title)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                """, (session_id, user_id, f"Test {i}"))
                
                # Insert pair
                user_msg = f"User message {i}"
                agent_msg = f"Agent response {i}"
                
                cursor.execute(
                    "INSERT INTO chat_history (user_id, session_id, role, content) VALUES (%s, %s, %s, %s)",
                    (user_id, session_id, "User", user_msg)
                )
                cursor.execute(
                    "INSERT INTO chat_history (user_id, session_id, role, content) VALUES (%s, %s, %s, %s)",
                    (user_id, session_id, "Agent", agent_msg)
                )
            
            conn.commit()
            
            # 3. Retrieve and Verify Order
            print("\nRetrieving history using seq_id sorting...")
            cursor.execute("""
                SELECT role, content, seq_id FROM (
                    SELECT role, content, seq_id FROM chat_history 
                    WHERE session_id = %s 
                    ORDER BY seq_id DESC LIMIT 10
                ) AS sub ORDER BY seq_id ASC
            """, (session_id,))
            
            rows = cursor.fetchall()
            
            correct = True
            for idx, row in enumerate(rows):
                expected_role = "User" if idx % 2 == 0 else "Agent"
                expected_num = idx // 2
                print(f"[{row['seq_id']}] {row['role']}: {row['content']}")
                
                if row['role'] != expected_role or str(expected_num) not in row['content']:
                    correct = False
            
            if correct:
                print("\n✅ SUCCESS: Message order is PERFECTLY stable.")
            else:
                print("\n❌ FAILURE: Message order is incorrect.")

if __name__ == "__main__":
    verify_sorting()
