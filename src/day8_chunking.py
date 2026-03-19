import warnings
warnings.filterwarnings("ignore")

import fitz
import re
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter
)
from sentence_transformers import SentenceTransformer
import chromadb
import uuid

print("="*50)
print("DAY 8 — CHUNKING STRATEGIES")
print("="*50)

# Load PDF first
def extract_full_text(pdf_path: str) -> str:
    """Extract all text from PDF as single string"""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()
    return full_text

def extract_pages(pdf_path: str) -> list[dict]:
    """Extract text page by page with metadata"""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if len(text) > 50:
            pages.append({
                "text": text,
                "page": i + 1
            })
    doc.close()
    return pages

print("\n Loading PDF...")
full_text = extract_full_text("../data/test.pdf")
pages = extract_pages("../data/test.pdf")
print(f" Loaded! Total chars: {len(full_text)}")
print(f" Valid pages: {len(pages)}")


# METHOD 1: FIXED SIZE CHUNKING

print("\n" + "="*50)
print("METHOD 1: Fixed Size Chunking")
print("="*50)

def fixed_size_chunks(
    text: str,
    chunk_size: int = 200,
    overlap: int = 20
) -> list[str]:
   
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk.split()) >= 15:
            chunks.append(chunk)
    
    return chunks

method1_chunks = fixed_size_chunks(
    full_text,
    chunk_size=200,
    overlap=20
)

print(f"Total chunks: {len(method1_chunks)}")
print(f"Avg words/chunk: {sum(len(c.split()) for c in method1_chunks) // len(method1_chunks)}")
print(f"\nSample chunk 1:")
print(f"{method1_chunks[0][:200]}...")
print(f"\nProblem — may split mid sentence:")
print(f"End of chunk 1:   ...{method1_chunks[0][-100:]}")
print(f"Start of chunk 2: {method1_chunks[1][:100]}...")


# METHOD 2: RECURSIVE CHARACTER SPLITTER

print("\n" + "="*50)
print("METHOD 2: Recursive Character Splitter")
print("="*50)

def recursive_chunks(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 100
) -> list[str]:
   
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    return splitter.split_text(text)

method2_chunks = recursive_chunks(
    full_text,
    chunk_size=1000,
    overlap=100
)

print(f"Total chunks: {len(method2_chunks)}")
print(f"Avg chars/chunk: {sum(len(c) for c in method2_chunks) // len(method2_chunks)}")
print(f"\nSample chunk 1:")
print(f"{method2_chunks[0][:200]}...")
print(f"\nBetter boundaries — ends at natural break:")
print(f"End of chunk 1: ...{method2_chunks[0][-100:]}")


# METHOD 3: PAGE-BASED CHUNKING

print("\n" + "="*50)
print("METHOD 3: Page-Based Chunking")
print("="*50)

def page_based_chunks(
    pages: list[dict]
) -> list[dict]:
   
    chunks = []
    for page_data in pages:
        text = page_data["text"]
        # Clean noise
        text = re.sub(r'\n+', ' ', text)
        text = text.strip()
        
        if len(text.split()) >= 15:
            chunks.append({
                "text": text,
                "page": page_data["page"]
            })
    return chunks

method3_chunks = page_based_chunks(pages)

print(f"Total chunks: {len(method3_chunks)}")
print(f"Avg words/chunk: {sum(len(c['text'].split()) for c in method3_chunks) // len(method3_chunks)}")
print(f"\nSample chunk (Page 1):")
print(f"{method3_chunks[0]['text'][:200]}...")

# COMPARISON — Which is Best?

print("\n" + "="*50)
print("COMPARISON TABLE")
print("="*50)

print(f"""
Method              | Chunks | Avg Size | Boundary | Best For
--------------------|--------|----------|----------|----------
Fixed Size          | {len(method1_chunks):6} | {sum(len(c.split()) for c in method1_chunks)//len(method1_chunks):8} words | Ignores  | Testing
Recursive Character | {len(method2_chunks):6} | {sum(len(c) for c in method2_chunks)//len(method2_chunks):8} chars | Respects | Production 
Page Based          | {len(method3_chunks):6} | {sum(len(c['text'].split()) for c in method3_chunks)//len(method3_chunks):8} words | Page     | Short docs
""")


# TEST — Which retrieves better?

print("="*50)
print("RETRIEVAL TEST — Same question, 3 methods")
print("="*50)

model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.Client()

test_question = "What are the prevention methods?"
q_embed = model.encode([test_question]).tolist()

# Store and test each method
methods = [
    ("Fixed Size", 
     method1_chunks, 
     None),
    ("Recursive", 
     method2_chunks, 
     None),
    ("Page Based", 
     [c["text"] for c in method3_chunks], 
     None),
]

print(f"\n Question: '{test_question}'")

for method_name, chunks, _ in methods:
    # Store in temp collection
    col = client.create_collection(
        name=method_name.lower().replace(" ", "_")
    )
    texts = chunks if isinstance(chunks[0], str) else [c["text"] for c in chunks]
    embeds = model.encode(texts).tolist()
    col.add(
        documents=texts,
        embeddings=embeds,
        ids=[str(uuid.uuid4()) for _ in texts]
    )
    
    # Search
    results = col.query(
        query_embeddings=q_embed,
        n_results=1
    )
    
    top_result = results["documents"][0][0]
    distance = results["distances"][0][0]
    
    print(f"\n {method_name}:")
    print(f"   Distance: {distance:.3f}")
    print(f"   Result: {top_result[:150]}...")