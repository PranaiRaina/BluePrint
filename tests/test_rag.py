from RAG_PIPELINE.src.ingestion import perform_similarity_search
from dotenv import load_dotenv
import os

load_dotenv()

def test_retrieval():
    print("🧪 Running RAG Integration Test...")
    try:
        # Test query
        test_query = "summarize"
        user_id = None # Search all
        print(f"Query: {test_query}")

        # Use the new robust search function
        results = perform_similarity_search(test_query, user_id=user_id, k=5)

        print(f"Found {len(results)} raw results.")
        
        if not results:
             print("⚠️ No results found. Ensure database is populated.")
        
        for doc, score in results:
            print(
                f"Score: {score:.4f} | Source: {doc.metadata.get('source')} | Content: {doc.page_content[:50]}..."
            )
            
        return len(results) > 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_retrieval()
