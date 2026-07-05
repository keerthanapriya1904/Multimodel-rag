# src/rag.py  —  UPDATED — 
# Pipeline: hybrid_search → MMR → rerank → semantic_cache → Groq
# 

import os, sys
sys.path.append(os.path.dirname(__file__))

from groq import Groq
from dotenv import load_dotenv
load_dotenv()

_groq_client = None

def get_groq():
    global _groq_client
    if _groq_client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise ValueError("GROQ_API_KEY not found in .env")
        _groq_client = Groq(api_key=key)
    return _groq_client


def build_context(chunks: list) -> str:
    """Build context string with source + page citations"""
    ctx = ""
    for i, c in enumerate(chunks):
        ctx += (f"\n[Source {i+1}: {c['source']} | "
                f"Page {c['page']}]\n{c['text']}\n")
    return ctx


def retrieve_chunks(question: str, user_id: str, n_final: int = 5):
    from ingestion import retrieve

    chunks = retrieve(question, user_id=user_id, n=n_final)

    print(f"[Dense] Retrieved {len(chunks)} chunks")

    return chunks

def ask_rag(question: str,
            user_id:  str ,
            chat_history:  list = None,
            stream:        bool = False) -> dict:
    """
    Full RAG pipeline with semantic cache:

    1. Check semantic cache → instant return if hit
    2. retrieve_chunks() → hybrid + MMR + rerank
    3. Build context with citations
    4. Groq LLaMA generates answer
    5. Store in semantic cache for future

    Args:
        question:     sanitized user question
        user_id:      which ChromaDB collection to search
        chat_history: last 6 turns for follow-up questions
        stream:       True = SSE token streaming

    Returns dict with:
        answer / stream, sources, chunks_used,
        cache_hit (bool)
    """
    # ── Step 1: Check semantic cache ─────────────────────────
    try:
        from semantic_cache import get_cache
        from ingestion import get_embed_model

        cache   = get_cache()
        model   = get_embed_model()
        q_embed = model.encode([question])[0].tolist()

        cached = cache.get(q_embed)
        if cached:
            # Cache hit — return instantly, no API call
            if stream:
                def cached_gen():
                    # Stream the cached answer token by token
                    for word in cached["answer"].split(" "):
                        yield word + " "
                return {
                    "stream":     cached_gen(),
                    "sources":    cached["sources"],
                    "chunks_used":cached["chunks_used"],
                    "cache_hit":  True
                }
            return cached

    except Exception as e:
        print(f"  [Cache] Error: {e} — skipping cache")
        q_embed = None

    # ── Step 2: Full retrieval pipeline ─────────────────────
    chunks = retrieve_chunks(question, user_id, n_final=3)

    if not chunks:
        no_docs = ("No documents found. Please upload a "
                   "document first using the Upload button.")
        if stream:
            def empty_gen():
                yield no_docs
            return {"stream": empty_gen(),
                    "sources": [], "chunks_used": 0,
                    "cache_hit": False}
        return {"answer": no_docs, "sources": [],
                "chunks_used": 0, "cache_hit": False}

    # ── Step 3: Build context ─────────    
    context = ""
    sources = []

    for chunk in chunks:
        context += (
            f"\n[Source: {chunk['source']} | Page: {chunk['page']} | Chunk: {chunk.get('chunk_id','-')}]"
            f"\n{chunk['text']}\n"
        )

        sources.append({
            "source": chunk["source"],
            "page": chunk["page"]
        })
    # ── Step 4: Build messages for Groq ───────
    system_prompt = (
        "You are a helpful document assistant for DocMind.\n"
        "STRICT RULES:\n"
        "1. Answer ONLY from the context provided below.\n"
        "2. Cite INLINE after each sentence: "
        "[Source: filename, Page N]\n"
        "3. If user asks for points/list/steps → use "
        "bullet format starting with - for each point.\n"
        "4. If user asks for numbered list → use 1. 2. 3.\n"
        "5. Use **bold** for key terms.\n"
        "6.if uses ask for an explation of a figure or table, provide a COMPREHENCIVE, step-by-step analysis, and use ALL the technical module names and labels provided in the context,and mainly do not summarize if the user asks for a detailed explation"
        "7. If answer not in context → say exactly: "
        "'This information is not in the uploaded documents.'\n"
        "8.  add information from your training data.\n\n"
        "Always use EXACT Page number from context. Do NOT guess or modify page numbers."
        f"CONTEXT:\n{context}"
        
    )

    messages = [{"role": "system", "content": system_prompt}]
    if chat_history:
        messages.extend(chat_history[-6:])
    messages.append({"role": "user", "content": question})

    # ── Step 5: Generate answer ──
    if stream:
        def stream_gen():
            full_answer = ""
            resp = get_groq().chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                max_tokens=1024,
                stream=True
            )
            for chunk in resp:
                token = chunk.choices[0].delta.content
                if token:
                    full_answer += token
                    yield token

            # Store in cache after full answer generated
            try:
                if q_embed and full_answer:
                    cache.set(user_id , q_embed, full_answer,
                              sources, len(chunks))
            except Exception:
                pass

        return {
            "stream":     stream_gen(),
            "sources":    sources,
            "chunks_used":len(chunks),
            "cache_hit":  False
        }

    # Non-streaming
    resp = get_groq().chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        max_tokens=1024,
        stream=False
    )
    answer = resp.choices[0].message.content

    # Store in cache
    try:
        if q_embed and answer:
            from semantic_cache import get_cache
            get_cache().set(user_id,q_embed, answer,
                            sources, len(chunks))
    except Exception:
        pass

    return {
        "answer":     answer,
        "sources":    sources,
        "chunks_used":len(chunks),
        "cache_hit":  False
    }


# ── Test 
if __name__ == "__main__":
   
    print("RAG PIPELINE TEST (with full Phase 4)")
    

    # Test 1: retrieve_chunks stages
    print("\nTest 1: retrieve_chunks() pipeline")
    chunks = retrieve_chunks("What is the main topic?",
                             user_id="test_user")
    print(f"  Final chunks returned: {len(chunks)}")
    for i, c in enumerate(chunks):
        score = c.get("rerank_score", "N/A")
        print(f"  {i+1}. Page {c['page']}: "
              f"{c['text'][:60]}... "
              f"[rerank={score}]")

    # Test 2: Full pipeline
    print("\nTest 2: ask_rag() full pipeline")
    result = ask_rag("What are the key findings?",
                     user_id="test_user")
    print(f"  Answer: {result['answer'][:200]}...")
    print(f"  Sources: {result['sources']}")
    print(f"  Cache hit: {result['cache_hit']}")

    # Test 3: Cache hit on same question
    print("\nTest 3: Same question — should be cache hit")
    result2 = ask_rag("What are the key findings?",
                      user_id="test_user")
    print(f"  Cache hit: {result2['cache_hit']} ← should be True")

    print("\nAll tests done!")
