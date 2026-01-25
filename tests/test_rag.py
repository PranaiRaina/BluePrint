
import asyncio
import sys
import os

from RAG_PIPELINE.src.graph import get_vectorstore

def test_retrieval():
    try:
        store = get_vectorstore()
        
        # Test query that should match the dummy upload
        test_query = "What is in the document?"
        print(f"Query: {test_query}")
        
        results = store.similarity_search_with_relevance_scores(test_query, k=5)
        
        print(f"Found {len(results)} raw results.")
        for doc, score in results:
            print(f"Score: {score:.4f} | Source: {doc.metadata.get('source')} | Content: {doc.page_content[:50]}...")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_retrieval()
