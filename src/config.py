import os
from pathlib import Path
from dotenv import load_dotenv

# ── FIX: Robust .env loading ──
# This finds the absolute path of the folder where config.py is located
# and looks for .env in that same folder.
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ── API Keys ─────
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_URL     = os.getenv("QDRANT_URL")
HF_TOKEN = os.getenv("HF_TOKEN")

# SECURE JWT SECRET
JWT_SECRET     = os.getenv("JWT_SECRET", "change-this-secret-key-32-chars!!")

# ── Embedding Models ────
EMBED_MODEL         = "all-MiniLM-L6-v2"          # 384-dim, English


# ── LLM ───
LLM_MODEL    = "llama-3.1-8b-instant"
VISION_MODEL = "gemini-3.5-flash"

# ── ChromaDB (Kept for local fallback) ───
CHROMA_PATH  = "./chroma_db"



# ── File Upload ────
UPLOAD_DIR      = "../data/uploads"
IMAGE_DIR       = "../data/images"
MAX_FILE_SIZE   = 10 * 1024 * 1024   # 10 MB
ALLOWED_TYPES   = {
    "application/pdf", 
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/jpg",
    "image/png"
}

# ── JWT Settings ────
JWT_ALGORITHM   = "HS256"
JWT_EXPIRE_MINS = 30

# ── RAG Settings ────────
CHUNK_SIZE      = 500
CHUNK_OVERLAP   = 50
RETRIEVE_TOP_N  = 5
MAX_TOKENS      = 1024


import re

def get_clean_name(filename: str) -> str:
    """
    Standardizes filenames to prevent metadata mismatches.
    Replaces special characters and spaces with underscores.
    """
    # 1. Remove user ID prefix if it exists
   
    # 2. Keep only letters, numbers, dots, and hyphens
    clean = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    return clean


# ── Test ────
if __name__ == "__main__":
    print("="*30)
    print("CONFIG SYSTEM AUDIT")
    print("="*30)
    print(f"  Groq key:   {' SET' if GROQ_API_KEY else ' MISSING'}")
    print(f"  Gemini key: {' SET' if GEMINI_API_KEY else ' MISSING'}")
    print(f"  Qdrant key: {' SET' if QDRANT_API_KEY else ' MISSING'}")
    print(f"  Qdrant URL: {' SET' if QDRANT_URL else ' MISSING'}")
    
    if not QDRANT_URL or "6333" in str(QDRANT_URL):
        print("   WARNING: URL might be wrong. Ensure no :6333 at the end.")
    
    print(f"  Max file:   {MAX_FILE_SIZE // (1024*1024)}MB")
   