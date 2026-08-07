from langchain_core.documents import Document

from RAG_PIPELINE.src.graph import describe_document

APR = Document(
    page_content="April 2025 rent payment.\n\n| 04/02/2025 | Rent | 1,650.00 |",
    metadata={
        "source": "specimen_bank_statement_apr2025.pdf",
        "doc_type": "bank_statement",
        "issuer": "Meridian Trust Bank",
        "period_ym": 202504,
    },
)


def test_describe_document_names_issuer_type_and_period():
    described = describe_document(APR)
    assert "Meridian Trust Bank" in described
    assert "Bank Statement" in described
    assert "April 2025" in described


def test_describe_document_survives_missing_metadata():
    described = describe_document(Document(page_content="x", metadata={}))
    assert isinstance(described, str)
    assert described


def test_describe_document_omits_absent_period():
    doc = Document(
        page_content="x",
        metadata={"doc_type": "receipt", "issuer": "Acme", "period_ym": None},
    )
    described = describe_document(doc)
    assert described == "Acme · Receipt"


def test_describe_document_distinguishes_two_months():
    mar = Document(
        page_content="x",
        metadata={
            "doc_type": "bank_statement",
            "issuer": "Meridian Trust Bank",
            "period_ym": 202503,
        },
    )
    assert describe_document(mar) != describe_document(APR)
