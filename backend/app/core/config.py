"""Application configuration."""
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment."""

    # Database
    database_url: str = "postgresql://localhost:5432/minuteslm"

    # Storage
    audio_upload_dir: Path = Path("uploads/audio")
    max_upload_mb: int = 100

    # ASR
    whisper_model: str = "turbo-v3"

    # LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
