import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from RAG_PIPELINE.src.ingestion import remove_pii, process_pdf_scoped
from RAG_PIPELINE.src.doc_metadata import DocumentMetadata

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

    def test_remove_pii_financial_identifiers(self):
        """Test redaction for financial document identifiers."""
        text = (
            "Mailing address: 123 Main Street, Riverside, CA 92521. "
            "Routing number: 021000021. "
            "Account number: 123456789012. "
            "Member ID: MBR-1234567. "
            "Passport number: 123456789. "
            "Driver license number: D1234567."
        )

        cleaned = remove_pii(text)

        for sensitive_value in [
            "123 Main Street",
            "021000021",
            "123456789012",
            "MBR-1234567",
            "123456789",
            "D1234567",
        ]:
            self.assertNotIn(sensitive_value, cleaned)

    def test_remove_pii_transaction_reference_ids(self):
        """Test redaction for transaction reference identifiers."""
        text = (
            "Zelle Ref ID: ZL123456789. "
            "Confirmation Number: 8K92LPA7. "
            "Transaction ID: TXN-948201. "
            "Trace ID: 1234567890."
        )

        cleaned = remove_pii(text)

        for sensitive_value in [
            "ZL123456789",
            "8K92LPA7",
            "TXN-948201",
            "1234567890",
        ]:
            self.assertNotIn(sensitive_value, cleaned)

    @patch("RAG_PIPELINE.src.ingestion.get_supabase_client")
    @patch("RAG_PIPELINE.src.ingestion.get_vectorstore")
    @patch("RAG_PIPELINE.src.ingestion.to_markdown")
    @patch("RAG_PIPELINE.src.ingestion.GoogleGenerativeAIEmbeddings")
    @patch("RAG_PIPELINE.src.ingestion.extract_document_metadata", new_callable=AsyncMock)
    @patch("RAG_PIPELINE.src.ingestion.summarize_chunks", new_callable=AsyncMock)
    async def test_process_pdf_scoped_duplicate(
        self, mock_summaries, mock_metadata, mock_embeddings,
        mock_to_markdown, mock_get_vs, mock_get_client,
    ):
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
    @patch("RAG_PIPELINE.src.ingestion.to_markdown")
    @patch("RAG_PIPELINE.src.ingestion.GoogleGenerativeAIEmbeddings")
    @patch("RAG_PIPELINE.src.ingestion.extract_document_metadata", new_callable=AsyncMock)
    @patch("RAG_PIPELINE.src.ingestion.summarize_chunks", new_callable=AsyncMock)
    async def test_process_pdf_scoped_success(
        self, mock_summaries, mock_metadata, mock_embeddings,
        mock_to_markdown, mock_get_vs, mock_get_client,
    ):
        """Test successful ingestion flow"""
        
        # Setup Mocks
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_vs = MagicMock()
        mock_get_vs.return_value = mock_vs
        
        mock_metadata.return_value = DocumentMetadata(
            doc_type="bank_statement",
            issuer="Meridian Trust Bank",
            period_start_ym=202505,
            period_end_ym=202505,
        )
        mock_summaries.return_value = ["May 2025 Meridian checking rent payment."]
        
        # Mock Duplicate Check -> No duplicate
        mock_execute_empty = MagicMock()
        mock_execute_empty.data = [] 
        
        mock_client.table.return_value \
            .select.return_value \
            .contains.return_value \
            .limit.return_value \
            .execute.return_value = mock_execute_empty

        mock_to_markdown.return_value = (
            "# Statement\n\n| Date | Description | Amount |\n|---|---|---|\n"
            "| 05/02/2025 | Payment - Rent | 1,650.00 |\n"
        )

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

    @patch("RAG_PIPELINE.src.ingestion.get_supabase_client")
    @patch("RAG_PIPELINE.src.ingestion.get_vectorstore")
    @patch("RAG_PIPELINE.src.ingestion.to_markdown")
    @patch("RAG_PIPELINE.src.ingestion.GoogleGenerativeAIEmbeddings")
    async def test_process_pdf_scoped_rejects_oversized_document(
        self, mock_embeddings, mock_to_markdown, mock_get_vs, mock_get_client
    ):
        """Oversized documents are rejected, never silently truncated."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_execute_empty = MagicMock()
        mock_execute_empty.data = []
        mock_client.table.return_value.select.return_value \
            .contains.return_value.limit.return_value \
            .execute.return_value = mock_execute_empty

        mock_to_markdown.return_value = "word " * 200_000

        result = await process_pdf_scoped("huge.pdf", b"huge", "user123")

        self.assertIn("too large", result.lower())
        mock_get_vs.return_value.add_texts.assert_not_called()

if __name__ == "__main__":
    unittest.main()
