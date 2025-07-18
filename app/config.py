import os
import secrets
from typing import List
from pydantic_settings import BaseSettings
from pydantic import validator

def get_database_url() -> str:
    """Get database URL with proper async driver"""
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        # Ensure we use asyncpg for PostgreSQL
        if "postgresql://" in db_url or "postgres://" in db_url:
            # Replace postgres:// with postgresql:// if needed
            db_url = db_url.replace("postgres://", "postgresql://")
            # Add asyncpg driver if not present
            if "+asyncpg" not in db_url:
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
            return db_url
        elif "sqlite" in db_url and "+aiosqlite" not in db_url:
            return db_url.replace("sqlite://", "sqlite+aiosqlite://")
        return db_url
    
    # Fallback for development
    return "sqlite+aiosqlite:///./strangers_meet.db"

def get_google_redirect_uri() -> str:
    """Get Google OAuth redirect URI based on environment"""
    frontend_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
    return f"{frontend_url}/api/v1/auth/google/callback"

class Settings(BaseSettings):
    PROJECT_NAME: str = "Strangers Meet"
    API_V1_STR: str = "/api/v1"
    
    # Environment detection
    ENVIRONMENT: str = os.getenv("RENDER", "production" if os.getenv("RENDER") else "development")
    
    # Base URL for frontend
    FRONTEND_URL: str = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = get_google_redirect_uri()

    # WhatsApp Gupshup settings
    GUPSHUP_API_KEY: str = os.getenv("GUPSHUP_API_KEY", "")
    GUPSHUP_SOURCE_NUMBER: str = os.getenv("GUPSHUP_SOURCE_NUMBER", "")
    GUPSHUP_APP_NAME: str = os.getenv("GUPSHUP_APP_NAME", "")
    GUPSHUP_TEMPLATE_ID: str = os.getenv("GUPSHUP_TEMPLATE_ID", "")
    
    # Database - FORCED asyncpg
    DATABASE_URL: str = get_database_url()
    
    # Debug mode
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # CORS origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://localhost:3000",
        os.getenv("RENDER_EXTERNAL_URL", ""),
        "https://timeleft.club",
        "https://www.timeleft.club"
    ]
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            origins = [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            origins = [origin for origin in v if origin]
        else:
            origins = []
        return origins
    
    @property
    def is_production(self) -> bool:
        return os.getenv("RENDER") is not None or self.ENVIRONMENT == "production"
    
    @property
    def use_https(self) -> bool:
        return self.is_production or self.FRONTEND_URL.startswith("https://")
    
    @property
    def session_secret(self) -> str:
        return os.getenv("SESSION_SECRET", self.SECRET_KEY)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()