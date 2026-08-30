from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "College RAG Assistant"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security
    AUTH_SECRET: str = Field(default="college_rag_jwt_secret_key_default_change_in_env")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ALGORITHM: str = "HS256"
    ALLOWED_ORIGINS: List[str] = ["*"]

    # MongoDB Cloud Database & Cloud File Storage
    DATABASE_TYPE: str = "mongodb"
    MONGODB_URI: str = Field(default="")
    MONGODB_DB_NAME: str = Field(default="college_rag")
    STORAGE_TYPE: str = "mongodb"
    UPLOAD_MAX_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".docx", ".txt", ".md", ".csv"]

    # RAG Configuration
    RAG_TOP_K: int = 20
    RAG_CONTEXT_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.35
    RAG_MAX_CONTEXT_TOKENS: int = 6000
    RAG_MAX_HISTORY_MESSAGES: int = 8
    HYBRID_SEARCH_ENABLED: bool = True
    RERANKER_ENABLED: bool = False
    OCR_ENABLED: bool = False

    # Chunking
    CHUNK_TARGET_SIZE: int = 750
    CHUNK_OVERLAP: int = 100
    CHUNK_MIN_SIZE: int = 120
    CHUNK_MAX_SIZE: int = 1200

    # LLM & Embedding Providers
    LLM_PROVIDER: str = "mock"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 1000

    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 384

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
