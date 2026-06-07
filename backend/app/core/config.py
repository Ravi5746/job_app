from pathlib import Path
from typing import List, Literal

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Job Automation Platform"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str
    GROQ_API_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int = 5432

    DATABASE_URL: str

    CORS_ORIGINS: List[str] = ["http://localhost:4000"]

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    RAPIDAPI_KEY: str = ""
    RAPIDAPI_HOST: str = "jsearch.p.rapidapi.com"

    NEXT_PUBLIC_API_URL: str = "http://localhost:8000/api/v1"
    
    OPENAI_API_KEY: str = ""
    TINYFISH_API_KEY: str = ""
    OPENAI_MODEL: str = "openai/gpt-oss-20b"

    # ── LLM Provider ──
    LLM_PROVIDER: Literal["groq", "ollama", "openrouter"] = "groq"

    # Groq models
    GROQ_MODEL_SMART: str = "llama-3.3-70b-versatile"   # Main form filling model
    GROQ_MODEL_FAST:  str = "llama-3.1-8b-instant"       # Fast classification / fallback

    # Ollama settings
    OLLAMA_BASE_URL:  str = "http://localhost:11434"
    OLLAMA_MODEL:     str = "llama3.3:70b"

    # ── Rate Limiting ──
    GROQ_REQUESTS_PER_SECOND: float = 0.4    # ~24 RPM
    GROQ_MAX_BUCKET_SIZE:     int   = 3

    # ── Agent Behaviour ──
    MAX_FORM_STEPS:    int = 15
    MAX_FILL_RETRIES:  int = 2
    LLM_TIMEOUT_SECS:  float = 12.0
    LLM_MAX_TOKENS:    int = 1000

    # ── LangSmith Observability ──
    LANGCHAIN_TRACING_V2:  str = "false"
    LANGCHAIN_API_KEY:     str = ""
    LANGCHAIN_PROJECT:     str = "job-applied-automation"

    HEADLESS: bool = False

    USER_DATA_DIR: str = str(Path.home() / ".job_applied_browser_data")
    SCREENSHOTS_DIR: str = str(Path.home() / ".job_applied_screenshots")
    UPLOAD_DIR: str = str(Path.home() / ".job_applied_uploads")

    class Config:
        env_file = BASE_DIR / ".env"
        case_sensitive = True
        extra = "allow"


settings = Settings()