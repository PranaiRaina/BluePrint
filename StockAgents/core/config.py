from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "Agentic Stock Analysis Tool"
    API_V1_STR: str = "/api/v1"

    # Security
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "stock_db"

    # Wolfram
    WOLFRAM_APP_ID: Optional[str] = None
    WOLFRAM_KEY_ID: Optional[str] = None
    WOLFRAM_KEY_SECRET: Optional[str] = None

    # Stock APIs
    ALPHA_VANTAGE_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    FINNHUB_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None

    # Formatting
    DISCLAIMER_TEXT: str = "Note: I am an AI financial analyst. My insights are for informational purposes — please verify strategies with a qualified professional."

    model_config = SettingsConfigDict(
        case_sensitive=True, env_file=".env", extra="ignore"
    )


settings = Settings()
