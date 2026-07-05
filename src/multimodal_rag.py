
# Unified query: text chunks + images → combined answer

import warnings
warnings.filterwarnings("ignore")

import os, sys
sys.path.append(os.path.dirname(__file__))

from groq import Groq
from dotenv import load_dotenv
from ingestion       import retrieve       as retrieve_text
from image_pipeline  import retrieve_images

load_dotenv()
_client = None

def get_groq():
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client

# ── Detect if question needs images 
def needs_images(question: str) -> bool:
    """
    Simple keyword router.
    If question mentions visuals → include image retrieval.
    """
    visual_keywords = [
        "diagram", "figure", "chart", "graph", "image", "picture",
        "show", "table", "illustration", "architecture", "flow",
        "screenshot", "visual", "draw", "sketch"
    ]
    q_lower = question.lower()
    return any(kw in q_lower for kw in visual_keywords)

# ── Build combined context 
def build_multimodal_context(text_chunks: list,
                              image_results: list) -> str:
    context = ""

    # Text context
    if text_chunks:
        context += "=== TEXT CONTENT ===\n"
        for i, chunk in enumerate(text_chunks):
            context += (f"[Source {i+1}: {chunk['source']} "
                        f"| Page {chunk['page']}]\n"
                        f"{chunk['text']}\n\n")

    # Image context
    if image_results:
        context += "=== IMAGE CONTENT ===\n"
        for i, img in enumerate(image_results):
            context += (f"[Image {i+1}: {img['source']} "
                        f"| Page {img['page']}]\n"
                        f"Description: {img['description']}\n"
                        f"Caption: {img.get('caption', 'None')}\n\n")

    return context

# ── Multimodal ask function ───────────────────────────────────
def ask_multimodal(
    question: str,
    user_id: str ,
    chat_history: list = None,
    stream: bool = False
) -> dict:
    """
    Routes question to text + image retrieval.
    Builds combined context and generates answer.
    """
    # Retrieve text chunks always
    text_chunks = retrieve_text(question, user_id=user_id, n=5)

    # Retrieve images only if question likely needs them
    image_results = []
    if needs_images(question):
        image_results = retrieve_images(question, user_id=user_id, n=3)

    # No results at all
    if not text_chunks and not image_results:
        return {"answer": "Please upload a document first.",
                "sources": [], "image_sources": [], "chunks_used": 0}

    # Build combined context
    context = build_multimodal_context(text_chunks, image_results)

    # Build messages
    messages = [{
        "role": "system",
        "content": ("You are DocMind, an AI assistant for document understanding."

                        "Rules:"
                        "1. Answer ONLY using the provided context."
                        "2. The context may contain:"
                            "- Extracted document text"
                            "- AI-generated descriptions of figures, tables, diagrams, charts and images"
                        "3. Combine both text and visual context whenever relevant."
                        "4. Never invent information or use outside knowledge."
                        "5. If only part of the answer is available, clearly state what is available."
                        "6. Add citations only at the end of a paragraph or bullet when all information comes from the same source."
                        "7. If multiple consecutive sentences come from the same page, use only ONE citation at the end."
                        "8. If information comes from different documents or pages, cite each section separately."
                        "9. Never repeat identical citations after every sentence."
                        "10. If the answer cannot be found, reply exactly:Not found in the uploaded documents."
                        "Follow the user's requested output format like Paragraph,Bullet points,Numbered list,Table,Comparison,Summary"
                        f"CONTEXT:\n{context}"
        )
    }]

    if chat_history:
        messages.extend(chat_history[-6:])

    messages.append({"role": "user", "content": question})

    # Sources for response
    text_sources  = [{"source": c["source"], "page": c["page"]}
                     for c in text_chunks]
    image_sources = [{"source": i["source"], "page": i["page"],
                      }
                     for i in image_results]

    if stream:
        def stream_gen():
            resp = get_groq().chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages, stream=True, max_tokens=1024
            )
            for chunk in resp:
                token = chunk.choices[0].delta.content
                if token:
                    yield token

        return {"stream": stream_gen(), "sources": text_sources,
                "image_sources": image_sources,
                "chunks_used": len(text_chunks) + len(image_results)}

    resp = get_groq().chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages, max_tokens=1024
    )
    return {
        "answer":        resp.choices[0].message.content,
        "sources":       text_sources,
        "image_sources": image_sources,
        "chunks_used":   len(text_chunks) + len(image_results)
    }

# ── Test ────
if __name__ == "__main__":
    print("=" * 50)
    print("MULTIMODAL RAG TEST")
    print("=" * 50)

    # Test routing
    print("\nneeds_images tests:")
    print(f"  'show me the diagram' → {needs_images('show me the diagram')}")
    print(f"  'what is RAG?'        → {needs_images('what is RAG?')}")

    # Test full multimodal query
    print("\nMultimodal Q&A:")
    result = ask_multimodal(
        "What are the main topics in this document?",
        user_id="keerthana"
    )
    print(f"Answer: {result['answer'][:200]}...")
    print(f"Text sources: {result['sources']}")
    print(f"Image sources: {result['image_sources']}")
