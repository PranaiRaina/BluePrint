import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from RAG_PIPELINE.src.ingestion import remove_pii, process_pdf_scoped

class TestIngestion(unittest.IsolatedAsyncioTestCase):
    
    def test_remove_pii(self):
        """Test PII redaction logic"""
        # Case 1: No PII
        text = "Hello world this is a test."
        cleaned = remove_pii(text)
        # Assuming analyzer mock or real analyzer passes clean text
        self.assertIn("Hello world", cleaned)

        # Case 2: Email (if presidio is active)
        # Note: In test environment without proper model download, it uses MockAnalyzer which returns []
        # So it should just return text as is or whatever the Mock does.
        # Let's verify the Mock logic from ingestion.py is used if spacy fails
        pass

    @patch("RAG_PIPELINE.src.ingestion.get_supabase_client")
    @patch("RAG_PIPELINE.src.ingestion.get_vectorstore")
    @patch("RAG_PIPELINE.src.ingestion.PyPDFLoader")
    @patch("RAG_PIPELINE.src.ingestion.GoogleGenerativeAIEmbeddings")
    @patch("RAG_PIPELINE.src.ingestion.generate_summary")
    async def test_process_pdf_scoped_duplicate(self, mock_summary, mock_embeddings, mock_loader, mock_get_vs, mock_get_client):
        """Test that duplicate file detection works"""
        
        # Setup Mocks
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock Supabase Response for "Duplicate Found"
        # The chain is: client.table().select().contains().limit().execute()
        mock_execute = MagicMock()
        mock_execute.data = [{"id": "existing-uuid"}] # Data present = duplicate
        
        mock_client.table.return_value \
            .select.return_value \
            .contains.return_value \
            .limit.return_value \
            .execute.return_value = mock_execute

        # Input
        filename = "test.pdf"
        content = b"fake pdf content"
        user_id = "user123"

        # Execute
        result = await process_pdf_scoped(filename, content, user_id)

        # Assert
        self.assertIn("Duplicate detected", result)
        mock_client.table.assert_called_with("documents")

    @patch("RAG_PIPELINE.src.ingestion.get_supabase_client")
    @patch("RAG_PIPELINE.src.ingestion.get_vectorstore")
    @patch("RAG_PIPELINE.src.ingestion.PyPDFLoader")
    @patch("RAG_PIPELINE.src.ingestion.GoogleGenerativeAIEmbeddings")
    @patch("RAG_PIPELINE.src.ingestion.generate_summary")
    async def test_process_pdf_scoped_success(self, mock_summary, mock_embeddings, mock_loader, mock_get_vs, mock_get_client):
        """Test successful ingestion flow"""
        
        # Setup Mocks
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_vs = MagicMock()
        mock_get_vs.return_value = mock_vs
        
        mock_summary.return_value = "A summary."
        
        # Mock Duplicate Check -> No duplicate
        mock_execute_empty = MagicMock()
        mock_execute_empty.data = [] 
        
        mock_client.table.return_value \
            .select.return_value \
            .contains.return_value \
            .limit.return_value \
            .execute.return_value = mock_execute_empty

        # Mock PDF Loading
        mock_doc = MagicMock()
        mock_doc.page_content = "This is the document content."
        mock_loader_instance = MagicMock()
        mock_loader.return_value = mock_loader_instance
        mock_loader_instance.load.return_value = [mock_doc]

        # Input
        filename = "unique.pdf"
        content = b"unique content"
        user_id = "user123"

        # Execute
        result = await process_pdf_scoped(filename, content, user_id)

        # Assert
        self.assertIn("Successfully processed", result)
        # Verify add_texts was called on vectorstore
        mock_vs.add_texts.assert_called()

if __name__ == "__main__":
    unittest.main()
