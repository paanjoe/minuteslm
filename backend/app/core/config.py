"""Application configuration."""
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment."""

    # Database
    database_url: str = "postgresql://localhost:5432/minuteslm"

    # Storage
    audio_upload_dir: Path = Path("uploads/audio")
    speaker_samples_dir: Path = Path("uploads/speakers")
    template_upload_dir: Path = Path("uploads/templates")
    detected_snippets_dir: Path = Path("uploads/detected_speakers")
    max_upload_mb: int = 1000

     
    whisper_model: str = "turbo-v3"
    # Long audio: chunk duration in seconds (e.g. 600 = 10 min). Audio longer than this is split and transcribed per chunk.
    transcription_chunk_duration_sec: int = 600

    # LLM (use OLLAMA_MODEL env to override; pull with: ollama pull qwen3.5)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5"
    # Context window (e.g. qwen3.5 = 4096). Long transcripts use head+tail to fit.
    ollama_context_tokens: int = 4096
    # Max tokens for model response; rest is used for prompt + transcript.
    ollama_max_output_tokens: int = 2048
    # If True, log the full prompt sent to Ollama when formatting (set LOG_LLM_PROMPT=1 in .env).
    log_llm_prompt: bool = False

    # Auth (dummy admin; replace with real auth later)
    admin_username: str = "admin"
    admin_password: str = "admin"
    admin_token: str = "admin"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
