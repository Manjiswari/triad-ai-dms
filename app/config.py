import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "triad-ai-dms-super-secret-key-production-32bytes-secure-2024")
    JWT_SECRET = os.getenv("JWT_SECRET", "triad-ai-jwt-secret-key-production-32bytes-secure-998877")
    JWT_EXPIRY = timedelta(hours=int(os.getenv("JWT_EXPIRY_HOURS", "24")))
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/dms_db")
    DB_NAME = os.getenv("DB_NAME", "dms_db")
    USE_MOCK_FALLBACK = os.getenv("USE_MOCK_FALLBACK", "true").lower() in ("true", "1", "yes")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "bmp", "txt"}
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")
