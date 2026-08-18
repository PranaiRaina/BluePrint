import os
import hashlib
from .chunk_summary import summarize_chunks
from .chunking import MAX_DOCUMENT_TOKENS, count_tokens, split_markdown
from .convert import to_markdown
from .doc_metadata import extract_document_metadata
from .llm_retry import retry_sync, with_retry
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client
from .config import settings

# PII Redaction
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

# Initialize Presidio
# Initialize Presidio (Lazy Loaded)
_analyzer = None
_anonymizer = None

PII_ENTITIES = [
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "US_SSN",
    "CREDIT_CARD",
    "LOCATION",
    "US_BANK_NUMBER",
    "IBAN_CODE",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "US_ROUTING_NUMBER",
    "BANK_ACCOUNT_NUMBER",
    "MEMBER_ID",
    "US_ADDRESS",
    "TRANSACTION_REFERENCE_ID",
]


# Every label-based recognizer below matches a keyword followed by a value.
# Without this the value part happily matches an ordinary English word, so
# "account" in a sentence swallows whatever follows it: "may treat the account
# as their own" redacted down to "may treat the <BANK_ACCOUNT_NUMBER>."
# Statements survived that because "account" there is followed by a number;
# agreements, KYC records and disclosures use the word in prose and were gutted.
#
# An identifier contains a digit. A word does not. Requiring one before the
# value is consumed is what separates them, and the value class excludes spaces
# so a match cannot run across words in the first place.
#
# The digit rule alone still ate short tokens sitting right after the label:
# "your account 401k contributions" and "the account 2024 forward" both look
# like identifiers to it. Real account, member and reference numbers run 7+
# characters, so the length floor drops those without touching anything real.
_ID_VALUE = r"(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{6,24}\b"


def _register_custom_pii_recognizers(analyzer: AnalyzerEngine) -> None:
    """Add finance-specific recognizers missing from Presidio's defaults."""
    recognizers = [
        PatternRecognizer(
            supported_entity="US_ROUTING_NUMBER",
            patterns=[
                Pattern(
                    "routing_number_with_label",
                    r"(?i)\b(?:routing|aba)\s*(?:number|no\.?|#)?\s*[:#-]?\s*\d{9}\b",
                    0.85,
                )
            ],
        ),
        PatternRecognizer(
            supported_entity="BANK_ACCOUNT_NUMBER",
            patterns=[
                Pattern(
                    "account_number_with_label",
                    r"(?i)\b(?:account|acct)\.?\s*(?:number|no\.?|#)?\s*[:#-]?\s*"
                    + _ID_VALUE,
                    0.85,
                )
            ],
        ),
        PatternRecognizer(
            supported_entity="MEMBER_ID",
            patterns=[
                Pattern(
                    "member_id_with_label",
                    r"(?i)\b(?:member|customer|client)\s*(?:id|number|no\.?|#)\s*"
                    r"[:#-]?\s*" + _ID_VALUE,
                    0.85,
                )
            ],
        ),
        PatternRecognizer(
            supported_entity="US_ADDRESS",
            patterns=[
                Pattern(
                    "street_address",
                    r"(?i)\b\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,5}\s+(?:street|st\.?|avenue|ave\.?|road|rd\.?|drive|dr\.?|lane|ln\.?|boulevard|blvd\.?|court|ct\.?|circle|cir\.?|way|place|pl\.?)\b(?:,\s*[A-Za-z .'-]+)?(?:,\s*[A-Z]{2})?(?:\s+\d{5}(?:-\d{4})?)?",
                    0.8,
                )
            ],
        ),
        PatternRecognizer(
            supported_entity="TRANSACTION_REFERENCE_ID",
            patterns=[
                Pattern(
                    "transaction_reference_with_label",
                    r"(?i)\b(?:zelle\s*(?:ref(?:erence)?|transaction)?\s*"
                    r"(?:id|number|no\.?|#)?|(?:transaction|reference|ref|"
                    r"confirmation|confirm|trace)\s*(?:id|number|no\.?|code|#)?)"
                    r"\s*[:#-]?\s*" + _ID_VALUE,
                    0.85,
                )
            ],
        ),
    ]

    for recognizer in recognizers:
        analyzer.registry.add_recognizer(recognizer)


def get_analyzer():
    global _analyzer
    if _analyzer is None:
        try:
            import spacy
            from presidio_analyzer.nlp_engine import SpacyNlpEngine

            # Explicitly configuration to use the installed 'en_core_web_sm' model
            # This prevents Presidio from searching for 'en_core_web_lg' and triggering auto-download
            if not spacy.util.is_package("en_core_web_sm"):
                raise RuntimeError("Spacy model 'en_core_web_sm' is not installed.")

            nlp_engine = SpacyNlpEngine(
                models=[{"lang_code": "en", "model_name": "en_core_web_sm"}]
            )
            _analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
            _register_custom_pii_recognizers(_analyzer)
        except Exception as e:
            print(f"Error initializing Presidio Analyzer: {e}")
            # Fallback to a mock/empty analyzer if everything fails, to allow ingestion to proceed
            print("WARNING: Proceeding without PII redaction.")

            class MockAnalyzer:
                def analyze(self, **kwargs):
                    return []

            _analyzer = MockAnalyzer()

    return _analyzer


def get_anonymizer():
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = AnonymizerEngine()
    return _anonymizer


def remove_pii(text: str) -> str:
    """
    Redact sensitive PII from text using Microsoft Presidio.
    Split into smaller blocks to prevent memory spikes/StreamReset.
    """
    if not text:
        return text

    try:
        analyzer = get_analyzer()
        anonymizer = get_anonymizer()

        # Process in 5000 character blocks to avoid memory/timeout issues
        block_size = 5000
        blocks = [text[i : i + block_size] for i in range(0, len(text), block_size)]
        clean_blocks = []

        for i, block in enumerate(blocks):
            # Analyze
            results = analyzer.analyze(
                text=block,
                entities=PII_ENTITIES,
                language="en",
            )
            # Anonymize
            anonymized_result = anonymizer.anonymize(
                text=block, analyzer_results=results
            )
            clean_blocks.append(anonymized_result.text)

        return "".join(clean_blocks)

    except Exception as e:
        print(f"PII Redaction Warning: {e}")
        # Fallback to original text if redaction fails, so user can still query
        return text


# Vector Store Wrapper
def get_supabase_client():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

def get_vectorstore():
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=settings.GOOGLE_API_KEY,
        task_type="retrieval_document",
        output_dimensionality=768,
    )
    
    client = get_supabase_client()
    
    return SupabaseVectorStore(
        client=client,
        embedding=embeddings,
        table_name="documents",
        query_name="match_documents"
    )

def perform_similarity_search(query: str, user_id: str, k: int = 5, threshold: float = 0.5):
    """
    Perform similarity search using direct RPC call to Supabase.
    Bypasses LangChain wrapper to avoid SDK compatibility issues.
    """
    try:
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=settings.GOOGLE_API_KEY,
            task_type="retrieval_query",
            output_dimensionality=768,
        )
        query_vector = retry_sync(embeddings.embed_query, query)
        
        client = get_supabase_client()
        
        params = {
            "query_embedding": query_vector,
            "match_threshold": threshold,
            "match_count": k,
            "filter": {"user_id": user_id} if user_id else {}
        }
        
        response = client.rpc("match_documents", params).execute()
        
        from langchain_core.documents import Document
        
        results = []
        for match in response.data:
            results.append(
                (
                    Document(
                        page_content=match["content"], 
                        metadata=match["metadata"]
                    ),
                    match["similarity"]
                )
            )
            
        return results
        
    except Exception as e:
        print(f"Error in similarity search: {e}")
        return []


async def extract_holdings_from_text(text: str) -> list:
    """
    Extract structured stock holdings from text using Gemini 2.5 Flash.
    Returns a list of dicts: {ticker, quantity, price, type}.
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", google_api_key=settings.GOOGLE_API_KEY
        )
        
        # Truncate for speed/cost - usually statements have holdings in first few pages or tables
        context = text[:15000] 
        
        prompt = f"""
        Analyze the following text (likely a brokerage statement or financial doc) and extract any stock/asset holdings.
        Return ONLY a JSON array of objects with these keys: "ticker" (str), "quantity" (float), "price" (float, optional), "asset_name" (str).
        If no holdings are found, return empty array [].
        Do not include markdown formatting like ```json.
        
        Text:
        {context}
        """
        
        response = await with_retry(llm).ainvoke(prompt)
        import json
        
        # Clean response (remove markdown if present)
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
            
        data = json.loads(content)
        return data if isinstance(data, list) else []
        
    except Exception as e:
        print(f"Extraction Error: {e}")
        return []


async def process_pdf_scoped(filename: str, file_content: bytes, user_id: str):
    """
    Ingest a PDF from memory: Hash -> Check Duplicate (scoped) -> Load -> PII Clean -> Summary -> Chunk -> Embed -> Store (scoped)
    """
    try:
        # 0. HASHING (Duplicate Check)
        file_hash = hashlib.sha256(file_content).hexdigest()

        vectorstore = get_vectorstore()
        supabase = get_supabase_client()

        # Check if hash exists in metadata FOR THIS USER
        response = supabase.table("documents").select("id").contains("metadata", {"file_hash": file_hash, "user_id": user_id}).limit(1).execute()

        if response.data:
            return f"Duplicate detected for user. {filename} already indexed."

        # 1. Convert to markdown
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            full_text = to_markdown(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # 2. Size limit. Reject rather than truncate - half a statement in the
        # index, with nothing marking the rest missing, is worse than no ingest.
        token_count = count_tokens(full_text)
        if token_count > MAX_DOCUMENT_TOKENS:
            return (
                f"Document too large: {token_count:,} tokens "
                f"(limit {MAX_DOCUMENT_TOKENS:,}). Please split it and re-upload."
            )

        # 3. PII Cleaning. Runs before every LLM call below, so no model sees
        # unredacted text.
        clean_text = remove_pii(full_text)

        # 4. Extraction Hook (Human-in-the-Loop)
        try:
            extracted_holdings = await extract_holdings_from_text(clean_text)
            if extracted_holdings:
                print(f"Extraction Hook Found {len(extracted_holdings)} items")

                # Save to Supabase holdings table (user-scoped)
                from ManagerAgent.holdings_db import upsert_holding

                for item in extracted_holdings:
                    item["source_doc"] = filename
                    item["status"] = "pending"  # pending until the user confirms
                    upsert_holding(user_id, item)

        except Exception as e:
            print(f"Extraction Hook Failed: {e}")

        # 5. Document metadata - type, issuer, period. Never embedded.
        meta = await extract_document_metadata(clean_text)

        # 6. Chunk on structure
        chunks = split_markdown(clean_text)
        if not chunks:
            return "No text found in PDF."

        # 7. One summary per chunk - the only text embedded alongside it
        summaries = await summarize_chunks(chunks, meta)

        base_metadata = {
            "file_hash": file_hash,
            "source": filename,
            "user_id": user_id,  # CRITICAL: Scoping
            "doc_type": meta.doc_type,
            "issuer": meta.issuer,
            # A range, not a month: a Jan-Mar statement is 202501..202503, so
            # "does this cover March" is one containment predicate on the jsonb
            # and works the same for monthly and quarterly documents.
            "period_start_ym": meta.period_start_ym,
            "period_end_ym": meta.period_end_ym,
        }

        texts = [
            f"{summary}\n\n{chunk}" for summary, chunk in zip(summaries, chunks)
        ]
        metadatas = [
            {**base_metadata, "chunk_index": i, "chunk_summary": summary}
            for i, summary in enumerate(summaries)
        ]

        # 8. Embed & Store
        retry_sync(vectorstore.add_texts, texts=texts, metadatas=metadatas)

        return f"Successfully processed {len(texts)} chunks for {filename}"

    except Exception as e:
        print(f"Error in scoped processing: {e}")
        raise e


async def delete_document_vectors_scoped(filename: str, user_id: str):
    """
    Delete all vectors associated with a specific filename and user_id.
    """
    try:
        supabase = get_supabase_client()
        
        # Scoped deletion via Supabase Client
        supabase.table("documents").delete().contains("metadata", {"source": filename, "user_id": user_id}).execute()

        return True
    except Exception as e:
        print(f"Error deleting scoped vectors: {e}")
        return False
