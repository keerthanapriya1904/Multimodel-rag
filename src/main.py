# src/main.py  (Render + Vercel + FastAPI)
# Run locally: uvicorn src.main:app --reload --port 8000

import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.ingestion import get_embed_model
from src.reranker import get_reranker


# Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)


# Rate Limiter

limiter = Limiter(key_func=get_remote_address)


# FastAPI App
app = FastAPI(
    title="DocMind — Multimodal RAG System",
    version="2.0.0",
    description="Privacy-first multimodal document Q&A system"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# CORS (React Frontend Support)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://your-frontend.vercel.app"  #  replace after deployment
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup (Load heavy models once)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting DocMind backend...")
    logger.info("DocMind backend started successfully.")
    logger.info("Models will be loaded on first use.")


# Global Error Handler

@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


# Routers

from api.auth import router as auth_router
from api.upload import router as upload_router
from api.query import router as query_router

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(query_router)


# Voice Router (optional safe import)

try:
    from voice_input import router as voice_router
    app.include_router(voice_router)
    logger.info("Voice router enabled ")
except ImportError:
    logger.warning("Voice feature disabled (voice_input not found)")


# Health Check Routes

@app.get("/")
def root():
    return {
        "app": "DocMind",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "2.0.0"
    }

