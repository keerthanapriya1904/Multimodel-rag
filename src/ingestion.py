import warnings
warnings.filterwarnings("ignore")

import os, sys, uuid, re, hashlib, requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import get_clean_name
# ── Master Cloud Connection ──
from src.vector_service import save_to_qdrant, search_qdrant

# Fix directory paths
sys.path.append(os.path.dirname(__file__))

# ── 1. EMBEDDING MODEL (Singleton - 90MB RAM) ──
_model = None
def get_embed_model():
    global _model
    if _model is None:
        # We tell Python to look in our local folder first
        local_path = "./models/bi-encoder"
        
        if os.path.exists(local_path):
            print("  [SYSTEM] Loading model from LOCAL DISK ")
            _model = SentenceTransformer(local_path)
        else:
            # Internet fallback
            _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# ── 2. EXTRACTION LOGIC (Multi-Source) ──

def extract_pdf(pdf_path: str) -> list:
    doc = fitz.open(pdf_path)
    pages = []
    for i in range(len(doc)):
        text = doc[i].get_text()
        text = re.sub(r'\n+', '\n', text).strip()
        if len(text) < 50: continue
        pages.append({
            "text": text,
            "page_num": i + 1,
            "source": os.path.basename(pdf_path)
        })
    doc.close()
    return pages

def extract_docx(docx_path: str) -> list:
    from docx import Document
    doc = Document(docx_path)
    text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return [{"text": text, "page_num": 1, "source": os.path.basename(docx_path)}]

def extract_txt(txt_path: str) -> list:
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()
    return [{"text": text, "page_num": 1, "source": os.path.basename(txt_path)}]

def extract_url(url: str) -> list:
    r = requests.get(url, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    text = re.sub(r'\n+', '\n', soup.get_text(separator="\n")).strip()
    return [{"text": text[:5000], "page_num": 1, "source": url[:50]}]

# ── 3. CHUNKING LOGIC ──
def chunk_pages(pages: list) -> list:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, chunk_overlap=50,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = []
    for page in pages:
        for chunk in splitter.split_text(page["text"]):
            if len(chunk.split()) < 15: continue
            chunks.append({
                "text": chunk,
                "page": page["page_num"],
                "chunk_id": str(uuid.uuid4())
            })
            
    return chunks

# ── 4. MASTER INGESTION (Qdrant Sydney Cloud) ──
# 
from src.config import get_clean_name

def ingest_document(file_path: str, user_id: str ) -> dict:
    """
    The 'Process-and-Purge' Pipeline:
    Extract -> Chunk -> Embed -> Sydney Sync
    """
    # --- NEW: Get the Clean Name immediately ---
    raw_filename= os.path.basename(file_path)
    master_id = get_clean_name(raw_filename)
   
    print(f"  [SYSTEM] Ingesting: {master_id}")
    ext = file_path.split(".")[-1].lower()

    if   ext == "pdf":  pages = extract_pdf(file_path)
    elif ext == "docx": pages = extract_docx(file_path)
    elif ext == "txt":  pages = extract_txt(file_path)
    elif file_path.startswith("http"): pages = extract_url(file_path)
    else: return {"error": f"Unsupported format: {ext}"}

    if not pages: return {"error": "Extraction failed"}

    chunks = chunk_pages(pages)
    if not chunks: return {"error": "No meaningful chunks created"}

    # Generate mathematical vectors
    print(f"  [SYSTEM] Generating vectors for {len(chunks)} chunks...")
    model = get_embed_model()
    embeddings = model.encode([c["text"] for c in chunks], show_progress_bar=False)

    for i, c in enumerate(chunks):
        c["vector"] = embeddings[i].tolist()
        c["type"] = "text_content"
        # --- NEW: Overwrite the source in chunk metadata with the clean name ---
        c["source"] = master_id 
        # -----------------------------------------------------------------------

    # SYNC TO CLOUD (Now uses the clean name in metadata)
    save_to_qdrant(chunks, user_id)

    return {
        "status": "success", 
        "pages": len(pages),
        "chunks": len(chunks), 
        "source": master_id # Return the clean name
    }

# ── 5. CLOUD RETRIEVAL ──
def retrieve(question: str, user_id: str , n: int = 5) -> list:
    """Fetches relevant chunks from Sydney Cloud Vault"""
    model = get_embed_model()
    q_vec = model.encode([question])[0].tolist()
    return search_qdrant(q_vec, user_id, limit=n)

if __name__ == "__main__":
    # Test logic
    print("Cloud Ingestion module ready.")