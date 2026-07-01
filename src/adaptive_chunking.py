# src/adaptive_chunking.py 
# Detects content type and chunks accordingly
# Tables → preserve as atomic units (don't split!)
# Code  → preserve with language tag
# Normal text → RecursiveCharacterTextSplitter
# pip install pdfplumber (already in requirements)

import sys, os, re
sys.path.append(os.path.dirname(__file__))
from langchain_text_splitters import RecursiveCharacterTextSplitter

def detect_content_type(text: str) -> str:
    """
    Detects what type of content a text block is.
    Returns: "table", "code", "list", "paragraph"
    """
    lines = text.strip().split("\n")

    # Table: multiple lines with | separators
    pipe_lines = sum(1 for l in lines if "|" in l)
    if pipe_lines >= 3:
        return "table"

    # Table: lines with consistent tab separation
    tab_lines = sum(1 for l in lines if "\t" in l and len(l.split("\t")) >= 3)
    if tab_lines >= 3:
        return "table"

    # Code: starts with def/class/import/function keywords
    code_keywords = ["def ", "class ", "import ", "from ", "function ",
                     "if __name__", "SELECT ", "CREATE TABLE", "const ",
                     "var ", "let ", "public class", "int main"]
    if any(text.strip().startswith(kw) for kw in code_keywords):
        return "code"

    # Code: high density of special characters
    special_chars = sum(1 for c in text if c in "{}()[];=><")
    if len(text) > 0 and special_chars / len(text) > 0.08:
        return "code"

    # List: many lines starting with bullet/number
    list_lines = sum(1 for l in lines if re.match(r'^[\s]*[\-\*\•\d\.]', l))
    if list_lines >= 3 and list_lines > len(lines) * 0.5:
        return "list"

    return "paragraph"

def extract_tables_from_pdf(pdf_path: str) -> list:
    """
    Uses pdfplumber to extract tables with their structure preserved.
    Returns list of {text, page, source, type="table"} dicts.
    """
    try:
        import pdfplumber
        tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                for table in page.extract_tables():
                    if not table:
                        continue
                    # Convert 2D table array to readable text
                    rows = []
                    for row in table:
                        row_text = " | ".join(
                            str(cell).strip() if cell else ""
                            for cell in row
                        )
                        rows.append(row_text)
                    table_text = "\n".join(rows)
                    if len(table_text.strip()) > 20:
                        tables.append({
                            "text":       table_text,
                            "page":       page_num + 1,
                            "source":     os.path.basename(pdf_path),
                            "type":       "table",
                            "word_count": len(table_text.split())
                        })
        return tables
    except Exception as e:
        print(f"  Table extraction error: {e}")
        return []

def adaptive_chunk(text: str, page: int, source: str,
                   chunk_size: int = 500, overlap: int = 50) -> list:
    """
    Chunks text based on detected content type:
    - table/code → keep as single chunk (never split!)
    - list → keep as single chunk
    - paragraph → RecursiveCharacterTextSplitter
    """
    content_type = detect_content_type(text)
    chunks = []

    if content_type in ("table", "code", "list"):
        # Preserve as atomic unit — never split these!
        if len(text.strip()) >= 20:
            chunks.append({
                "text":       text.strip(),
                "page":       page,
                "source":     source,
                "type":       content_type,
                "word_count": len(text.split())
            })
    else:
        # Normal paragraph text — use recursive splitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        for chunk in splitter.split_text(text):
            if len(chunk.split()) >= 15:
                chunks.append({
                    "text":       chunk,
                    "page":       page,
                    "source":     source,
                    "type":       "paragraph",
                    "word_count": len(chunk.split())
                })
    return chunks

def adaptive_ingest(pdf_path: str, user_id: str ) -> dict:
    """
    Full adaptive ingestion pipeline:
    1. Extract tables with pdfplumber (preserve structure)
    2. Extract text with PyMuPDF
    3. Detect content type for each block
    4. Chunk appropriately
    5. Embed and store in ChromaDB
    """
    import uuid
    import chromadb
    from ingestion import get_embed_model

    all_chunks = []

    # Step 1: Extract tables first (pdfplumber preserves structure)
    tables = extract_tables_from_pdf(pdf_path)
    all_chunks.extend(tables)
    print(f"  Tables found: {len(tables)}")

    # Step 2: Extract text with PyMuPDF + adaptive chunking
    import fitz
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page     = doc[page_num]
        blocks   = page.get_text("blocks")
        for block in blocks:
            text = block[4].strip()
            if len(text) < 30:
                continue
            chunks = adaptive_chunk(
                text, page_num + 1, os.path.basename(pdf_path)
            )
            all_chunks.extend(chunks)
    doc.close()

    if not all_chunks:
        return {"error": "No content extracted"}

    # Step 3: Embed and store
    model      = get_embed_model()
    texts      = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, show_progress_bar=False)

    client     = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(
        name=f"user_{user_id}",
        metadata={"hnsw:space": "cosine"}
    )
    collection.add(
        documents=texts,
        embeddings=embeddings.tolist(),
        ids=[str(uuid.uuid4()) for _ in all_chunks],
        metadatas=[{"page":       c["page"],
                    "source":     c["source"],
                    "type":       c.get("type", "paragraph"),
                    "word_count": c["word_count"],
                    "user_id":    user_id}
                   for c in all_chunks]
    )
    type_counts = {}
    for c in all_chunks:
        t = c.get("type", "paragraph")
        type_counts[t] = type_counts.get(t, 0) + 1

    print(f"  Stored {len(all_chunks)} chunks: {type_counts}")
    return {"status": "success", "chunks": len(all_chunks),
            "type_breakdown": type_counts}

if __name__ == "__main__":
    text1 = "Name | Age | Score\nAlice | 23 | 95\nBob | 25 | 87"
    text2 = "def hello():\n    print('world')\n    return True"
    text3 = "RAG is a technique that combines retrieval with generation."

    print(f"Table detected:     {detect_content_type(text1)}")
    print(f"Code detected:      {detect_content_type(text2)}")
    print(f"Paragraph detected: {detect_content_type(text3)}")
