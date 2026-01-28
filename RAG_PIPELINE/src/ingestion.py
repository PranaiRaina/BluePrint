import os
import hashlib
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from .config import settings
import chromadb

# PII Redaction
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

# Initialize Presidio
# Initialize Presidio (Lazy Loaded)
_analyzer = None
_anonymizer = None

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
                
            nlp_engine = SpacyNlpEngine(models=[{"lang_code": "en", "model_name": "en_core_web_sm"}])
            _analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        except Exception as e:
            print(f"Error initializing Presidio Analyzer: {e}")
            # Fallback to a mock/empty analyzer if everything fails, to allow ingestion to proceed
            print("WARNING: Proceeding without PII redaction.")
            class MockAnalyzer:
                def analyze(self, **kwargs): return []
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
    """
    try:
        analyzer = get_analyzer()
        anonymizer = get_anonymizer()
        
        # Analyze
        results = analyzer.analyze(text=text, entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN", "CREDIT_CARD"], language='en')
        # Anonymize
        anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized_result.text
    except Exception as e:
        print(f"PII Redaction Warning: {e}")
        return text

# Initialize Chroma
# We use the PersistentClient to run locally without Docker
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Vector Store Wrapper
def get_vectorstore():
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=settings.GOOGLE_API_KEY)
    return Chroma(
        client=chroma_client,
        collection_name="rag_documents",
        embedding_function=embeddings
    )

async def generate_summary(text: str) -> str:
    """
    Generate a 2-sentence summary of the document for global context.
    """
    try:
        # Dynamic LLM Selection
        # Defaulting to Gemini 2.0 Flash (OpenAI Compatible) for speed 
        # But for LangChain, ChatGoogleGenerativeAI is native and easy
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=settings.GOOGLE_API_KEY)

        # Truncate to first 10k chars to avoid token limits on large docs
        prompt = f"Summarize the following document in 2 sentences to provide global context:\n\n{text[:10000]}"
        response = await llm.ainvoke(prompt)
        return response.content
    except Exception as e:
        print(f"Summary Generation Warning: {e}")
        return "Global context summary unavailable."

async def process_pdf(file_path: str):
    """
    Ingest a PDF file: Hash -> Check Duplicate -> Load -> PII Clean -> Summary -> Chunk -> Embed -> Store
    """
    try:
        # 0. HASHING (Duplicate Check)
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        vectorstore = get_vectorstore()
        
        # Check if hash exists in metadata
        # Note: Chroma's get method allows filtering by metadata
        existing = vectorstore.get(where={"file_hash": file_hash})
        if existing and existing['ids']:
            return f"Duplicate detected. Document with hash {file_hash[:8]}... already exists."

        # 1. Load
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        full_text = "\n".join([doc.page_content for doc in documents])
        
        # 2. PII Cleaning
        clean_text = remove_pii(full_text)
        
        # 3. Global Summary
        summary = await generate_summary(clean_text)
        
        # 4. Contextual Chunking
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        raw_chunks = text_splitter.split_text(clean_text)
        
        # Add Context to chunks
        contextual_chunks = []
        metadatas = []
        filename = os.path.basename(file_path)
        
        for i, chunk in enumerate(raw_chunks):
            # Prepend summary
            augmented_text = f"Document: {filename}\nGlobal Summary: {summary}\n\nContent: {chunk}"
            
            contextual_chunks.append(augmented_text)
            metadatas.append({
                "file_hash": file_hash,
                "source": filename,
                "chunk_index": i,
                "summary": summary
            })
        
        if not contextual_chunks:
            return "No text found in PDF."

        # 5. Embed & Store
        vectorstore.add_texts(texts=contextual_chunks, metadatas=metadatas)
        
        return f"Successfully processed {len(contextual_chunks)} chunks for {filename} (Hash: {file_hash[:8]}...)"
    
    except Exception as e:
        print(f"Error processing PDF: {e}")
        raise e
