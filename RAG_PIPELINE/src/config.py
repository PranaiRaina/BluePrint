from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG Pipeline MVP"
    
    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: str = "8000"
    
    # API Keys
    GOOGLE_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    
    # Configuration
    LLM_PROVIDER: str = "gemini" # Options: "gemini", "groq"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
