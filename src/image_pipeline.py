import os
import sys
import gc
import time
import io
from PIL import Image
import fitz  # PyMuPDF
import google.generativeai as genai


# Local module imports (Assuming these exist in your project)
from config import GEMINI_API_KEY, VISION_MODEL
from vector_service import save_to_qdrant, get_qdrant

# Fix path for imports safely
sys.path.append(os.path.dirname(__file__))

# — 1. SETUP VISION AI (Gemini 3.5 Flash) —
genai.configure(api_key=GEMINI_API_KEY)



vision_model = genai.GenerativeModel(VISION_MODEL) 
def get_image_description(img: Image.Image) -> str:
    """
    UNIVERSAL VISION ENGINE (GEMINI)
    Receives an in-memory PIL Image of a full PDF page.
    """

    universal_prompt = (
        "ACT AS A MULTIMODAL DATA EXTRACTION EXPERT. You are looking at a full page of a document. "
        "You are looking at either a PDF page, a scanned document, a JPG/JPEG image, or a PNG image. "
        "Extract every piece of useful information while preserving technical accuracy. "
        "Locate any Figures, Architecture Diagrams, Flowcharts, or Tables on this page and convert them "
        "into a high-fidelity text proxy for a retrieval system. Ignore standard body paragraphs.\n\n"
        "STEP 1: CATEGORIZE. Identify if the visual is a Table, Chart, Flowchart, Diagram, or Photo.\n"
        "STEP 2: EXTRACT BASED ON TYPE:\n"
        " - IF TABLE: Extract every row and column into a structured Markdown table.\n"
        " - IF CHART/GRAPH: Identify the legend and transcribe the exact numerical data points.\n"
        " - IF FLOWCHART/ARCHITECTURE: Describe the logic flow using arrows (-->) to show connections.\n"
        " - IF DIAGRAM: Label every component and explain their spatial relationship.\n"
        " - IF PHOTO/IMAGE: Describe the subject, any visible text (OCR), and the background context.\n"
        "STEP 3: OCR. Transcribe every single word, number, and label found inside the diagram/image.\n\n"
        "CRITICAL RULE: DO NOT SUMMARIZE. DO NOT OMIT DATA. Provide granular technical detail."
        "Give the citation only once if the source and page is same "
    )

    try:
        # --- RESOLUTION COMPRESSION FOR TPM MITIGATION ---
        MAX_SIZE = 1200  
        if img.width > MAX_SIZE or img.height > MAX_SIZE:
            img.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)

        response = vision_model.generate_content([universal_prompt, img])
        return response.text
    except Exception as e:
        if "429" in str(e):
            return "quota_hit"
        print(f"[Vision Error] {e}")
        return "failed"


# — 2. IMAGE EXTRACTION (Page Rasterization & Memory Optimized) —
def extract_images_from_pdf(pdf_path: str):
    """
    Takes a single high-quality screenshot of the entire rendered page.
    This preserves arrows, layout, and text for complex composite diagrams.
    Generates in-memory image streams to protect RAM.
    """
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Only process pages that actually contain images or vector drawings
        if len(page.get_images()) > 0 or len(page.get_drawings()) > 0:
            
            # get_pixmap takes a "screenshot" of the page. 
            # dpi=150 is  enough for AI but keeps the file size small.
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            
            yield {
                "img_stream": io.BytesIO(img_bytes),
                "page": page_num + 1,
                "source": os.path.basename(pdf_path),
                "img_index": 0 # Defaulting to 0 since it represents the whole page
            }
            
    doc.close()


# — 3. INGESTION (Embedding Optimized & 429 Protected) —
def ingest_images(pdf_path: str, user_id: str):
    from ingestion import get_embed_model
    
    print(f"[Vision] Starting Page-Rasterized Universal Extraction for {pdf_path}...")
    
    # Load embedding model into RAM once
    model = get_embed_model() 
    processed_count = 0  

    # Consume the generator one page at a time
    for img_data in extract_images_from_pdf(pdf_path):
        try:
            with Image.open(img_data["img_stream"]) as pil_img:
                description = get_image_description(pil_img)
                
                # --- 429 EXPONENTIAL BACKOFF LOGIC ---
                max_retries = 4
                retry_count = 0
                base_delay = 15
                
                while description == "quota_hit" and retry_count < max_retries:
                    retry_count += 1
                    print(f"   [QUOTA] API limit hit. Attempt {retry_count}/{max_retries}. Waiting {base_delay}s...")
                    time.sleep(base_delay)
                    description = get_image_description(pil_img)
                    base_delay *= 2 
                
                # If STILL a quota hit after 4 retries, daily limit is likely exhausted.
                if description == "quota_hit":
                    print("   [QUOTA EXHAUSTED] Gemini API daily limit reached. Stopping ingestion for now.")
                    break # Safely exit the loop and stop processing this PDF

                if description != "failed":
                    full_text = f"VISUAL DATA (Page {img_data['page']}): {description}"
                    
                    # Embedding optimized: Create list of floats directly
                    vector = model.encode(full_text).tolist()

                    save_to_qdrant([{
                        "text": full_text, 
                        "vector": vector,
                        "source": img_data["source"], 
                        "page": img_data["page"],
                        "img_index": img_data["img_index"],
                        "content_type": "image_description"
                    }], user_id)

                    processed_count += 1
                    print(f"   [DB] Synced Multimodal Proxy for Page {img_data['page']} 🌅")

                    # RPM Defensive Throttle (Stay under 15 requests per minute)
                    time.sleep(5) 
            
        except Exception as e:
            print(f"   [Ingestion Error] {e}")
            continue
        finally:
            # Close stream to free RAM immediately after processing each page
            img_data["img_stream"].close()
            gc.collect()

    # Clean up embedding model from RAM after ingestion is complete
    del model
    gc.collect()
    
    return {"images_stored": processed_count}

def ingest_single_image(image_path: str, user_id: str):
    """
    Ingest a standalone JPG/JPEG/PNG image into Qdrant.
    """
    from ingestion import get_embed_model
    print(f"[Vision] Processing image: {image_path}")
    model = get_embed_model()
    processed = 0
    try:
        with Image.open(image_path) as img:
            description = get_image_description(img)
            if description == "failed":
                return {"images_stored": 0}
            if description == "quota_hit":
                return {"images_stored": 0}
            vector = model.encode(description).tolist()
            save_to_qdrant([{
                "text": description,
                "vector": vector,
                "source": os.path.basename(image_path),
                "page": 1,
                "img_index": 0,
                "content_type": "image_description"
            }], user_id)

            processed = 1
    except Exception as e:
        print(f" [Ingestion Error] {e}")
    finally:
        del model
        gc.collect()

    return {"images_stored": processed}
# — 4. RETRIEVAL & SNAPSHOT EXPLANATION (In-Memory Page Render) —
def retrieve_images(question: str, user_id: str , n: int = 3) -> list:
    """
    SEARCH LOGIC: Finds relevant image descriptions in the Sydney Cloud Vault.
    """
    from qdrant_client.http import models
    from vector_service import get_qdrant
    from ingestion import get_embed_model
    
    # 1. Connect to the Sydney Cloud Cluster
    client = get_qdrant()
    collection_name = f"user_{user_id}"

    # 2. Turn the question into a 384-dim vector
    model = get_embed_model()
    q_vec = model.encode([question])[0].tolist()
    
    try:
        # 3. PERFORM THE SEARCH with Metadata Filter
        # This ensures we only pull Image Descriptions, not regular text.
        results = client.query_points(
            collection_name=collection_name,
            query_vector=q_vec,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="content_type", 
                        match=models.MatchValue(value="image_description")
                    )
                ]
            ),
            limit=n,
            with_payload=True
        )
        
        # 4. Return results formatted for multimodal_rag.py
        return [{
            "description": r.payload["text"],
            "page": r.payload["page"],
            "source": r.payload["source"],
            "score": r.score
        } for r in results]
    except Exception as e:
        print(f"  [Vision Search Error] {e}")
        return []



