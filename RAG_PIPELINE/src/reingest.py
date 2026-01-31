import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from RAG_PIPELINE.src.ingestion import process_pdf_scoped
from RAG_PIPELINE.src.config import settings

load_dotenv()

async def reingest_all_documents():
    """
    Scans the 'rag-documents' bucket for ALL files (across all user folders),
    downloads them, and re-ingests them into the new Supabase Vector Store.
    """
    print("🚀 Starting Re-ingestion: Storage Bucket -> Postgres Vector Store")
    
    # 1. Initialize Supabase Client (Service Role for Admin Access)
    # We need Service Key to list ALL folders in the bucket
    if not settings.SUPABASE_SERVICE_KEY:
        print("❌ Error: SUPABASE_SERVICE_KEY is missing. Cannot proceed.")
        return

    supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    bucket_name = "rag-documents"

    try:
        # 2. List all User Folders (Top Level)
        # Using list() on root to find folders (which represent user_ids)
        root_list = supabase.storage.from_(bucket_name).list()
        
        user_folders = [item['name'] for item in root_list if item['id'] is None] # Folders often have id=None or metadata indicating folder
        # Fallback: Just try to recursivly list or assume top level names are user_ids if they look like UUIDs
        # A safer way if structure is known: 
        # The app uploads to: user_id/filename.pdf
        
        print(f"📂 Found {len(root_list)} items in root (Potential User Folders)")

        total_processed = 0
        total_errors = 0

        for folder in root_list:
            user_id = folder['name']
            
            # Skip likely non-user files at root if any
            if "." in user_id: 
                continue

            print(f"\nScanning User: {user_id}")
            
            # List files in this user's folder
            files = supabase.storage.from_(bucket_name).list(path=user_id)
            
            for file_obj in files:
                filename = file_obj['name']
                if not filename.endswith(".pdf"):
                    continue
                
                print(f"  ⬇️  Downloading: {filename}")
                file_path = f"{user_id}/{filename}"
                
                try:
                    # Download file content
                    data = supabase.storage.from_(bucket_name).download(file_path)
                    
                    # Process (Chunk -> Embed -> Store)
                    # process_pdf_scoped expects bytes
                    print(f"  ⚙️  Processing...")
                    result = await process_pdf_scoped(filename, data, user_id)
                    print(f"  ✅  {result}")
                    total_processed += 1
                
                except Exception as e:
                    print(f"  ❌  Failed to process {filename}: {e}")
                    total_errors += 1

    except Exception as e:
        print(f"Global Error during re-ingestion: {e}")

    print("\n------------------------------------------------")
    print(f"🎉 Re-ingestion Complete.")
    print(f"✅ Success: {total_processed}")
    print(f"❌ Failed:  {total_errors}")
    print("------------------------------------------------")

if __name__ == "__main__":
    asyncio.run(reingest_all_documents())
