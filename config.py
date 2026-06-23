import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "chatapp-secret-key")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 60,
        "pool_size": 1,
        "max_overflow": 0,
        "connect_args": {
            "sslmode": "require",
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5
        }
    }