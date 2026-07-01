# src/web_search.py  
# DuckDuckGo web search (NO API KEY needed, completely free)
# pip install duckduckgo-search
# Supplements document answers with current web information

import sys, os
sys.path.append(os.path.dirname(__file__))

def search_web(query: str, max_results: int = 3) -> list:
    """
    Search DuckDuckGo for current information.
    Returns list of result dicts with title, url, snippet.

    No API key needed! DuckDuckGo is free to use.
    """
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title",   ""),
                    "url":     r.get("href",    ""),
                    "snippet": r.get("body",    "")[:500],
                    "source":  "web_search"
                })
        return results
    except ImportError:
        print("  duckduckgo-search not installed. Run: pip install duckduckgo-search")
        return []
    except Exception as e:
        print(f"  Web search error: {e}")
        return []

def should_use_web_search(question: str, doc_chunks: list) -> bool:
    """
    Decides whether to supplement with web search.
    Use web search if:
    1. No document chunks were found, OR
    2. Question asks about current/recent events
    """
    if not doc_chunks:
        return True

    current_keywords = [
        "today", "current", "latest", "now", "recent", "2024", "2025", "2026",
        "news", "update", "price", "stock", "weather", "who is", "what is the current"
    ]
    q_lower = question.lower()
    return any(kw in q_lower for kw in current_keywords)

def ask_with_web_search(question: str, user_id: str = None ,
                         chat_history: list = None) -> dict:
    """
    Enhanced RAG that adds web search when needed.
    Falls back to web results if no documents uploaded.
    """
    from rag import ask_rag, build_context
    from ingestion import retrieve

    # Get document chunks
    doc_chunks = retrieve(question, user_id=user_id, n=5)

    # Decide if web search needed
    web_results = []
    if should_use_web_search(question, doc_chunks):
        print(f"  Web search triggered for: '{question[:50]}'")
        web_results = search_web(question, max_results=3)

    if not doc_chunks and not web_results:
        return {"answer": "No documents uploaded and web search returned no results.",
                "sources": [], "web_sources": []}

    # Build combined context
    context = ""
    if doc_chunks:
        context += build_context(doc_chunks)
    if web_results:
        context += "\n=== WEB SEARCH RESULTS ===\n"
        for i, r in enumerate(web_results):
            context += f"\n[Web {i+1}: {r['title']} | URL: {r['url']}]\n{r['snippet']}\n"

    # Generate answer using Groq
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    messages = [{"role": "system", "content": (
        "You are a helpful assistant. Answer from the context below.\n"
        "For document sources cite: Source X, Page Y.\n"
        "For web sources cite: Web X (URL).\n"
        "If not in context say: 'Not found in available sources.'\n\n"
        f"CONTEXT:\n{context}"
    )}]
    if chat_history:
        messages.extend(chat_history[-6:])
    messages.append({"role": "user", "content": question})

    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant", messages=messages, max_tokens=1024)

    return {
        "answer":      resp.choices[0].message.content,
        "sources":     [{"source": c["source"], "page": c["page"]} for c in doc_chunks],
        "web_sources": [{"title": r["title"], "url": r["url"]} for r in web_results]
    }

if __name__ == "__main__":
    print("Testing web search...")
    results = search_web("what is RAG in AI", max_results=2)
    print(f"Got {len(results)} web results")
    for r in results:
        print(f"  - {r['title'][:60]}")
