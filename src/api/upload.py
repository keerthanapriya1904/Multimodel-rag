import sys, os, re
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from database import User
from api.auth import get_current_user
from ingestion import ingest_document
from vector_service import purge_file_vectors
from config import UPLOAD_DIR, MAX_FILE_SIZE, ALLOWED_TYPES

# ── Master Cloud Service ──
from vector_service import get_qdrant 
from qdrant_client.http import models

router = APIRouter(prefix="/upload", tags=["Upload"])
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # 1. Validation
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Format {file.content_type} not supported.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large (Max 10MB).")

    # 2. Safe Save (Temporary)
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)

    cloud_identity = f"{current_user.id}_{safe_name}"
    file_path = os.path.join(UPLOAD_DIR, cloud_identity)
    
    with open(file_path, "wb") as f:
        f.write(content)

    filename_to_check = file.filename
    try:
        print(f"[DB] checking if {filename_to_check} already exists in the vault")
        purge_file_vectors(cloud_identity, current_user.id)
    except Exception as e:
        pass
    
    # 3. TEXT & TABLE Ingestion (Syncs to Sydney)
    
    text_result = ingest_document(file_path, user_id=current_user.id)
    
    # 4. MULTIMODAL Ingestion (Auto-trigger Vision for PDFs)
    images_stored = 0
    if safe_name.lower().endswith(".pdf"):
        try:
            from image_pipeline import ingest_images
            img_result = ingest_images(file_path, user_id=current_user.id)
            images_stored = img_result.get("images_stored", 0)
        except Exception as e:
            print(f"  [Vision] Pipeline skipped: {e}")

    # 5. ZERO-PERSISTENCE: Shred raw file from disk
    if os.path.exists(file_path):
        os.remove(file_path)

    return {
        "message": "Knowledge synced to Cloud Vault. Local file purged.",
        "filename": file.filename,
        "chunks": text_result.get("chunks", 0),
        "images": images_stored
    }

@router.get("/list")
def list_uploads(current_user: User = Depends(get_current_user)):
    """Fetches unique document names from Sydney Cloud"""
    try:
        client = get_qdrant()
        collection_name = f"user_{current_user.id}"
        
        # Scroll through the cloud database to find unique filenames
        results, _ = client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        
        sources = list(set([r.payload["source"] for r in results]))
        return {"documents": sources}
    except Exception:
        return {"documents": []}


@router.delete("/{filename}")
def delete_document(filename: str, current_user: User = Depends(get_current_user)):
    try:
        # We need to make sure the filename from the URL is cleaned
        clean_name = str(filename)
        purge_file_vectors(clean_name, current_user.id)
        return {"message": f"Successfully deleted {clean_name}"}
    except Exception as e:
        print(f"  [DELETE ERROR] {e}")
        raise HTTPException(status_code=500, detail="Cloud purge failed.")

         


