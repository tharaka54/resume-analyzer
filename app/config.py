"""
app/config.py — Configuration loaded from .env
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-fallback")
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    # MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/resume_analyzer")

    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/auth/callback")

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    GOOGLE_SCOPES = ["openid", "email", "profile"]

    # JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-fallback")
    JWT_ACCESS_EXPIRES_MINUTES = int(os.getenv("JWT_ACCESS_EXPIRES_MINUTES", 60))
    JWT_REFRESH_EXPIRES_DAYS = int(os.getenv("JWT_REFRESH_EXPIRES_DAYS", 30))

    # Claude API
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # File Upload
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))  # 5 MB
    ALLOWED_EXTENSIONS = {"pdf"}

    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
