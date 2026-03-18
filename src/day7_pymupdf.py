import warnings
warnings.filterwarnings("ignore")

import fitz  # PyMuPDF
import os


print(" PyMuPDF PDF EXTRACTION")
print("="*50)

# ── PART 1: BASIC TEXT EXTRACTION ──
print("\n Part 1: Basic Text Extraction")

def extract_text_basic(pdf_path: str) -> None:
   
    
    doc = fitz.open(pdf_path)
    
    print(f"PDF: {pdf_path}")
    print(f"Total pages: {len(doc)}")
    print(f"Title: {doc.metadata.get('title', 'Unknown')}")
    print(f"Author: {doc.metadata.get('author', 'Unknown')}")
    
    for page_num in range(min(3, len(doc))):
        page = doc[page_num]
        text = page.get_text()
        
        print(f"\n--- Page {page_num + 1} ---")
        print(f"Characters: {len(text)}")
        print(f"Preview: {text[:200]}...")
    
    doc.close()

extract_text_basic("../data/test.pdf")

# ── PART 2: STRUCTURED EXTRACTION ──
print("\n\n Part 2: Structured Extraction")

def extract_structured(pdf_path: str) -> list[dict]:
   
    doc = fitz.open(pdf_path)
    pages = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        
        # Clean basic noise
        text = text.strip()
        
        # Skip empty pages
        if len(text) < 50:
            print(f"  Page {page_num+1} skipped — too short!")
            continue
            
        pages.append({
            "text": text,
            "page_num": page_num + 1,
            "char_count": len(text),
            "word_count": len(text.split()),
        })
    
    doc.close()
    return pages

pages = extract_structured("../data/test.pdf")
print(f" Extracted {len(pages)} valid pages!")
print(f"Total words: {sum(p['word_count'] for p in pages)}")
print(f"Average words per page: {sum(p['word_count'] for p in pages) // len(pages)}")

# ── PART 3: IMAGE EXTRACTION ──
print("\n\n Part 3: Image Extraction")

def extract_images(pdf_path: str, output_dir: str) -> list[dict]:
   
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    images = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images()
        
        for img_idx, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # Save image
            image_name = f"page{page_num+1}_img{img_idx+1}.{image_ext}"
            image_path = os.path.join(output_dir, image_name)
            
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            
            images.append({
                "path": image_path,
                "page": page_num + 1,
                "size": len(image_bytes),
                "format": image_ext
            })
            
    doc.close()
    return images

images = extract_images("../data/test.pdf", "../data/extracted_images")
print(f" Extracted {len(images)} images!")

if images:
    for img in images[:3]:
        print(f"  → Page {img['page']}: {img['path']} ({img['size']} bytes)")
else:
    print("  → No images found in this PDF")
    print("  → Try a PDF with diagrams or figures!")

# ── PART 4: WORD COUNT STATS ──
print("\n\n Part 4: PDF Statistics")

def get_pdf_stats(pages: list[dict]) -> None:
    
    
    total_words = sum(p['word_count'] for p in pages)
    total_chars = sum(p['char_count'] for p in pages)
    
    # Estimate tokens (words × 1.33)
    estimated_tokens = int(total_words * 1.33)
    
    print(f"Total pages extracted: {len(pages)}")
    print(f"Total words: {total_words}")
    print(f"Total characters: {total_chars}")
    print(f"Estimated tokens: {estimated_tokens}")
    print(f"\nToken limit comparison:")
    print(f"  llama-3.1-8b limit:  8,192 tokens")
    print(f"  Your PDF tokens:     {estimated_tokens}")
    
    if estimated_tokens > 8192:
        print(f"   TOO LARGE for direct LLM!")
        print(f"   RAG required! Chunks solve this!")
    else:
        print(f"   Fits in context window!")
        print(f"  But RAG still better for accuracy!")

get_pdf_stats(pages)


# ── PART 5: FULL INGESTION PIPELINE ──
print("\n\n Part 5: Full Ingestion Pipeline")

import chromadb
from sentence_transformers import SentenceTransformer
import uuid

def chunk_pages(
    pages: list[dict],
    chunk_size: int = 200,
    overlap: int = 20
) -> list[dict]:
    
    chunks = []
    
    for page_data in pages:
        text = page_data["text"]
        page_num = page_data["page_num"]
        words = text.split()
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            
            # Skip tiny chunks
            if len(chunk_words) < 15:
                continue
                
            chunks.append({
                "text": " ".join(chunk_words),
                "page": page_num,
                "chunk_index": len(chunks),
                "word_count": len(chunk_words)
            })
    
    return chunks

# Step 1: Chunk
print("\n  Chunking pages...")
chunks = chunk_pages(pages, chunk_size=200, overlap=20)
print(f" Created {len(chunks)} chunks!")
print(f"Sample: {chunks[0]['text'][:100]}...")

# Step 2: Embed
print("\n Embedding chunks...")
embed_model = SentenceTransformer("all-MiniLM-L6-v2")
texts = [c["text"] for c in chunks]
embeddings = embed_model.encode(
    texts,
    show_progress_bar=True
)
print(f" Embeddings shape: {embeddings.shape}")

# Step 3: Store
print("\n Storing in ChromaDB...")
client = chromadb.PersistentClient(
    path="./chroma_db_day8"
)
collection = client.get_or_create_collection(
    name="bank_security_pdf",
    metadata={"hnsw:space": "cosine"}
)

collection.add(
    documents=texts,
    embeddings=embeddings.tolist(),
    ids=[str(uuid.uuid4()) for _ in chunks],
    metadatas=[{
        "page": c["page"],
        "chunk_index": c["chunk_index"],
        "word_count": c["word_count"],
        "source": "test.pdf"
    } for c in chunks]
)
print(f" Stored {collection.count()} chunks!")

# Step 4: Test search
print("\n Testing search...")

questions = [
    "What are the prevention methods for data leaks?",
    "How did insider employees cause bank fraud?",
    "What happened between 2023 and 2025 in Indian banks?",
]

for question in questions:
    q_embed = embed_model.encode([question]).tolist()
    results = collection.query(
        query_embeddings=q_embed,
        n_results=2,
        include=["documents", "distances", "metadatas"]
    )
    
    print(f"\n {question}")
    for doc, dist, meta in zip(
        results["documents"][0],
        results["distances"][0],
        results["metadatas"][0]
    ):
        print(f"   Page {meta['page']} "
              f"(dist: {dist:.3f}): "
              f"{doc[:80]}...")