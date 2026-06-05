from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="ai-dev-os", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    backend_cors_origins: str = Field(default="http://localhost:3000", alias="BACKEND_CORS_ORIGINS")
    database_url: str = Field(default="postgresql+asyncpg://ai_dev_os:ai_dev_os_password@localhost:5432/ai_dev_os", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_chat_model: str = Field(default="qwen2.5-coder:latest", alias="OLLAMA_CHAT_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text:latest", alias="OLLAMA_EMBED_MODEL")
    chroma_persist_directory: str = Field(default="./vector_store/chroma", alias="CHROMA_PERSIST_DIRECTORY")
    repositories_root: str = Field(default="./repositories", alias="REPOSITORIES_ROOT")
    max_file_size_bytes: int = Field(default=1_000_000, alias="MAX_FILE_SIZE_BYTES")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    tree_sitter_language_library: str = Field(default="", alias="TREE_SITTER_LANGUAGE_LIBRARY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
