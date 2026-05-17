import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
    VECTOR_STORE_PATH = os.path.join(os.path.dirname(__file__), "vector_store")
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "knowledgebase")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 100
    TOP_K_RESULTS = 8
