"""
StatuteLens configuration — loads settings from .env file.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://dev:dev@localhost:5432/statutelens"

    # LLM
    GEMINI_API_KEY: Optional[str] = None

    # Voice (ElevenLabs)
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_AGENT_ID: str = ""
    ELEVENLABS_VOICE_ID: str = "TxGEqnHWrfWFTfGW9XjX"  # "Josh" — deep, professional male

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # App
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:8000"]
    LOG_LEVEL: str = "info"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
