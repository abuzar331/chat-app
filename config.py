import os
from dotenv import load_dotenv

load_dotenv()

IS_PRODUCTION = os.getenv("RENDER") is not None

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "chatapp-secret-key")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 60,
        "pool_size": 1,
        "max_overflow": 0,
        "connect_args": {"sslmode": "require"} if IS_PRODUCTION else {}
    }