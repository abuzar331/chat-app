import os
from dotenv import load_dotenv
load_dotenv()
class Config:
    SQLALCHEMY_DATABASE_URI =os.getenv ( "DATABASE_URL",

        "postgresql://postgres:Abu%408530@localhost:5432/chatapp"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = os.getenv("SECRET_KEY", "chatapp-secret-key")