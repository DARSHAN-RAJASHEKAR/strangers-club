import os
import secrets
from typing import Optional, Dict, Any, List
from pydantic_settings import BaseSettings
from pydantic import validator

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
    
    @property
    def GOOGLE_REDIRECT_URI(self) -> str:
        """Dynamic redirect URI based on environment"""
        if self.FRONTEND_URL and self.FRONTEND_URL != "http://localhost:8000":
            return f"{self.FRONTEND_URL}/api/v1/auth/google/callback"
        return "http://localhost:8000/api/v1/auth/google/callback"
    
    # Database - FIXED: Proper async driver handling
    DATABASE_URL: str = ""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.DATABASE_URL = self._get_database_url()
    
    def _get_database_url(self) -> str:
        """Get database URL with proper async driver"""
        db_url = os.getenv("DATABASE_URL")
        
        if db_url:
            # Convert postgres:// to postgresql+asyncpg:// for async SQLAlchemy
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return db_url
        
        # Fallback for development
        return "sqlite+aiosqlite:///./strangers_meet.db"
    
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
    def parse_cors_origins(cls, v: Any) -> List[str]:
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

# Debugging info
if os.getenv("RENDER"):
    print(f"🚀 Running on Render: {settings.FRONTEND_URL}")
    print(f"📊 Database: {settings.DATABASE_URL.split('@')[0]}@[HIDDEN]")
    
    if "sqlite" in settings.DATABASE_URL:
        print("⚠️  WARNING: Using SQLite - data will be lost on restart!")
    else:
        print("✅ Using PostgreSQL with async driver - data will persist!")
        
    if settings.GOOGLE_CLIENT_ID and "localhost" in settings.GOOGLE_REDIRECT_URI:
        print(f"⚠️  Update Google OAuth redirect to: {settings.GOOGLE_REDIRECT_URI}")