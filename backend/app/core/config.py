from pathlib import Path
from typing import List

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

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    CORS_ORIGINS: List[str] = ["http://localhost:4000"]

    RAPIDAPI_KEY: str = ""
    RAPIDAPI_HOST: str = "jsearch.p.rapidapi.com"

    NEXT_PUBLIC_API_URL: str = "http://localhost:8000/api/v1"
    
    OPENAI_API_KEY: str = ""
    TINYFISH_API_KEY: str = ""
    OPENAI_MODEL: str = "openai/gpt-oss-20b"

    HEADLESS: bool = False

    USER_DATA_DIR: str = str(Path.home() / ".job_applied_browser_data")
    SCREENSHOTS_DIR: str = str(Path.home() / ".job_applied_screenshots")
    UPLOAD_DIR: str = str(Path.home() / ".job_applied_uploads")

    class Config:
        env_file = BASE_DIR / ".env"
        case_sensitive = True
        extra = "allow"


settings = Settings()