from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # App
    app_name: str = "internal-ai-advisory-assistant"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    # Auth
    auth_enabled: bool = True
    api_key: str = Field(default="dev-key-change-me", min_length=8)
    
    # LLM
    llm_provider: Literal["openai", "azure", "local"] = "openai"
    openai_api_key: str = Field(default="", description="OpenAI API key")
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    
    llm_model: str = "gpt-4-turbo-preview"
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2048, ge=1, le=128000)
    llm_timeout: int = Field(default=60, ge=1, le=300)
    
    # Embeddings
    embedding_provider: Literal["openai", "sentence-transformers"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = Field(default=1536, ge=1)
    
    # Vector DB
    vector_db_provider: Literal["qdrant", "faiss"] = "qdrant"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "advisory_documents"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_path: str = "./data/vector_store"
    
    # Retrieval
    retrieval_top_k: int = Field(default=10, ge=1, le=100)
    retrieval_min_score: float = Field(default=0.5, ge=0.0, le=1.0)
    
    hybrid_enabled: bool = True
    hybrid_dense_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    hybrid_sparse_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    rrf_k: int = Field(default=60, ge=1)
    
    @field_validator("hybrid_sparse_weight")
    @classmethod
    def validate_weights(cls, v: float, info) -> float:
        return v
    
    # Processing
    chunk_size: int = Field(default=512, ge=100, le=2048)
    chunk_overlap: int = Field(default=64, ge=0, le=512)
    min_chunk_size: int = Field(default=100, ge=10)
    supported_extensions: str = ".pdf,.docx,.md,.txt"
    
    @property
    def supported_extensions_list(self) -> list[str]:
        return [ext.strip().lower() for ext in self.supported_extensions.split(",")]
    
    # Paths
    data_raw_path: str = "./data/raw"
    data_processed_path: str = "./data/processed"
    feedback_db_path: str = "./data/feedback.db"
    
    # Rate Limit
    rate_limit_enabled: bool = True
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window: int = Field(default=60, ge=1)
    
    # Monitoring
    log_format: Literal["json", "console"] = "json"
    
    # Flags
    feature_feedback_enabled: bool = True
    feature_intent_detection_enabled: bool = True
    feature_structured_output_enabled: bool = True
    
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
    
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
