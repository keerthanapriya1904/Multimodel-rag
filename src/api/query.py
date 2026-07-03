# src/api/query.py 
# CHANGES:
#   1. Expanded sanitization layer (30+ injection patterns)
#   2. Unicode control character stripping
#   3. HTML tag stripping before sending to LLM
#   4. Zero persistence policy — chat_histories in memory only,
#      never written to disk or database
#   5. Rate limiting on query endpoint
#   6. Input length hard cap

import sys, os, json, re, unicodedata
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, validator
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from database      import User
from api.auth      import get_current_user
from agent_router  import agent_orchestrator   # ← agentic routing
from rag           import ask_rag              # ← fallback

router  = APIRouter(prefix="/query", tags=["Query"])
limiter = Limiter(key_func=get_remote_address)

# ── ZERO PERSISTENCE POLICY ───────────────────────────────────
# Chat histories live ONLY in this in-memory dict.
# They are NEVER written to disk, database, or any file.
# When the server restarts, all histories are cleared.
# This is intentional — privacy-first design.
# If you need persistence, use an encrypted Redis cache.
chat_histories: dict = {}   # {user_id: [{role, content}, ...]}

# ── Request model ─────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    stream:   Optional[bool] = False

    @validator("question")
    def question_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()

# ── SANITIZATION LAYER ────────────────────────────────────────
# 30+ prompt injection and jailbreak patterns
INJECTION_PATTERNS = [
    # Classic prompt injection
    "ignore previous instructions",
    "ignore all instructions",
    "ignore the above",
    "disregard previous",
    "forget your instructions",
    "override your instructions",
    "new instructions:",
    "updated instructions:",
    "system prompt:",
    "system message:",
    # Jailbreak attempts
    "act as",
    "pretend you are",
    "you are now",
    "roleplay as",
    "simulate being",
    "jailbreak",
    "dan mode",
    "developer mode",
    "unrestricted mode",
    "bypass restrictions",
    # API key / secrets extraction
    "reveal api key",
    "show api key",
    "what is your api key",
    "print your secret",
    "reveal your prompt",
    "show your system prompt",
    "what are your instructions",
    "output your instructions",
    # HTML / script injection
    "<script",
    "javascript:",
    "onload=",
    "onerror=",
    "onclick=",
    # Path traversal
    "../",
    "..\\",
]

def strip_html(text: str) -> str:
    """Remove all HTML tags from text"""
    return re.sub(r"<[^>]+>", "", text)

def strip_control_chars(text: str) -> str:
    """
    Remove Unicode control characters.
    These can be used to hide malicious instructions
    that are invisible to humans but visible to LLMs.
    """
    return "".join(
        ch for ch in text
        if not unicodedata.category(ch).startswith("C")
        or ch in ("\n", "\t")   # keep newlines and tabs
    )

def normalise_whitespace(text: str) -> str:
    """Collapse multiple spaces/newlines to single"""
    text = re.sub(r"[ \t]{3,}", "  ", text)   # max 2 spaces
    text = re.sub(r"\n{4,}", "\n\n\n", text)   # max 3 newlines
    return text.strip()

def sanitize_question(raw: str) -> tuple[str, str | None]:
    """
    Full sanitization pipeline for user input.

    Returns:
        (clean_text, None)         — if safe
        (None, "reason")           — if rejected

    Steps:
        1. Length check
        2. Strip HTML tags
        3. Strip control characters
        4. Check injection patterns
        5. Normalise whitespace
        6. Final length trim
    """
    # Step 1: Hard length limits
    if len(raw) < 3:
        return None, "Question too short (minimum 3 characters)"
    if len(raw) > 2000:
        raw = raw[:2000]   # hard truncate — don't error, just trim

    # Step 2: Strip HTML tags
    text = strip_html(raw)

    # Step 3: Strip control characters (invisible Unicode tricks)
    text = strip_control_chars(text)

    # Step 4: Check for injection patterns
    lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lower:
            return None, f"Query contains restricted content: '{pattern}'"

    # Step 5: Normalise whitespace
    text = normalise_whitespace(text)

    # Step 6: Final sanity check
    if len(text.strip()) < 3:
        return None, "Question too short after sanitization"

    return text, None

# ── Query endpoint ────────────────────────────────────────────
@router.post("/")
@limiter.limit("10/minute")    # max 10 queries per minute per IP
async def query(request: Request,req: QueryRequest, current_user: User = Depends(get_current_user)):
    
    # ── Sanitize ─────────────────────────────────────────────
    clean_question, error = sanitize_question(req.question)
    if error:
        raise HTTPException(status_code=400, detail=error)

    # ── Get in-memory history (zero persistence policy) ──────
    # This dict is process-local — never touches disk
    history = chat_histories.get(current_user.id, [])

    # ── Route via agent orchestrator ─────────────────────────
    if req.stream:
        result = agent_orchestrator(
            clean_question,
            user_id=current_user.id,
            chat_history=history,
            stream=True
        )

        def event_gen():
            full_answer = ""
            try:
                for token in result["stream"]:
                    full_answer += token
                    # SSE format: "data: <token>\n\n"
                    yield f"data: {token}\n\n"

                # Send sources after final token
                sources_json = json.dumps({
                    "sources":     result["sources"],
                    "chunks_used": result["chunks_used"]
                })
                yield f"data: [SOURCES]{sources_json}\n\n"
                yield "data: [DONE]\n\n"

                # Update in-memory history
                # ZERO PERSISTENCE: never written to disk
                history.append({"role": "user",      "content": clean_question})
                history.append({"role": "assistant", "content": full_answer})
                chat_histories[current_user.id] = history[-10:]

            except Exception as e:
                yield f"data: [ERROR]{str(e)}\n\n"

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control":   "no-cache",
                "X-Accel-Buffering": "no",
                "X-Content-Type-Options": "nosniff"   # security header
            }
        )

    # ── Non-streaming response ────────────────────────────────
    result = agent_orchestrator(
        clean_question,
        user_id=current_user.id,
        chat_history=history
    )

    # Update in-memory history (zero persistence)
    history.append({"role": "user",      "content": clean_question})
    history.append({"role": "assistant", "content": result["answer"]})
    chat_histories[current_user.id] = history[-10:]

    return {
        "answer":      result["answer"],
        "sources":     result["sources"],
        "chunks_used": result["chunks_used"],
        "question":    clean_question,
        "tool_used":   result.get("tool_used", "PDF_RETRIEVER")
    }

# ── History endpoints ─────────────────────────────────────────
@router.delete("/history")
def clear_history(current_user: User = Depends(get_current_user)):
    """Clear in-memory chat history for current user"""
    chat_histories[current_user.id] = []
    return {"message": "History cleared"}

@router.get("/history")
def get_history(current_user: User = Depends(get_current_user)):
    """Get current session history (in-memory only)"""
    return {
        "history": chat_histories.get(current_user.id, []),
        "note":    "History is session-only — not persisted to disk"
    }
