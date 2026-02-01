from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG Pipeline MVP"

    # API Keys
    GOOGLE_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    # Supabase Postgres
    SUPABASE_DB_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # Configuration
    LLM_PROVIDER: str = "gemini"  # Options: "gemini"

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )


settings = Settings()
