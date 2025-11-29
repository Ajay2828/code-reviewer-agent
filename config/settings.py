from pydantic_settings import BaseSettings
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application
    APP_NAME: str = "Code Review Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # API Keys
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    GITHUB_TOKEN: Optional[str] = None
    GITLAB_TOKEN: Optional[str] = None
    
    # LLM Configuration
    PRIMARY_LLM: str = "claude-sonnet-4-20250514"
    FALLBACK_LLM: str = "gpt-4-turbo"
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.1
    STREAMING: bool = True
    
    # Agent Configuration
    MAX_ITERATIONS: int = 3
    ENABLE_SELF_REFLECTION: bool = True
    CONFIDENCE_THRESHOLD: float = 0.7
    
    # Cost Management
    COST_LIMIT_PER_REVIEW: float = 1.0  # USD
    ENABLE_COST_TRACKING: bool = True
    CACHE_TTL: int = 3600  # 1 hour
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Database
    DATABASE_URL: str = "sqlite:///./code_reviews.db"
    DB_ECHO: bool = False
    
    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # API Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    CORS_ORIGINS: List[str] = ["*"]
    
    # Webhook
    WEBHOOK_SECRET: Optional[str] = None
    ENABLE_WEBHOOKS: bool = True
    
    # Supported Languages
    SUPPORTED_LANGUAGES: List[str] = [
        "python", "javascript", "typescript", 
        "go", "java", "rust", "cpp"
    ]
    
    # Static Analysis Tools
    ENABLE_RUFF: bool = True
    ENABLE_PYLINT: bool = True
    ENABLE_ESLINT: bool = True
    ENABLE_SEMGREP: bool = True
    
    # Review Configuration
    MAX_FILE_SIZE: int = 100000  # 100KB
    MAX_FILES_PER_REVIEW: int = 50
    REVIEW_TIMEOUT: int = 300  # 5 minutes
    
    # Metrics
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Cost tracking constants
COST_PER_1K_TOKENS = {
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-opus-4-20250514": {"input": 0.015, "output": 0.075},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "text-embedding-3-small": {"input": 0.00002, "output": 0},
}


# Severity levels for issues
class Severity:
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


# Issue categories
class IssueCategory:
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    BEST_PRACTICE = "best_practice"