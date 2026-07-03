import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PORT: int = int(os.getenv("PORT", 5000))
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", 3306))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "smart_ration_db")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super_secret_key")
    JWT_EXPIRES_IN: str = os.getenv("JWT_EXPIRES_IN", "7d")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5000")

settings = Settings()
