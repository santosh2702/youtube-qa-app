"""
main.py — Entry point of the YouTube Q&A FastAPI application.

WHAT'S SAME as PDF project:
  - FastAPI app setup
  - CORS middleware
  - Startup event to load models
  - Router registration pattern

WHAT'S NEW vs PDF project:
  - ChromaDB initialized at startup (not just models)
  - Two routers: video (replaces pdf) and qa
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import video, qa
from app.services.model_service import ModelService
from app.services.vector_store import vector_store

app = FastAPI(
    title="YouTube Q&A API",
    description="Paste a YouTube URL, then ask questions about the video using free HuggingFace models.",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Same as PDF project — React on :3000 needs permission to call API on :8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ───────────────────────────────────────────────────────────────────
# NEW vs PDF project:
# We now initialize TWO things at startup:
#   1. HuggingFace models (same as before)
#   2. ChromaDB client (new — creates/opens the on-disk database)
@app.on_event("startup")
async def startup():
    print("🔄 Loading HuggingFace models...")
    ModelService.load_all()
    print("✅ Models loaded!")

    print("🗄️  Initializing ChromaDB...")
    vector_store.init()
    print("✅ ChromaDB ready!")

# ── Routers ───────────────────────────────────────────────────────────────────
# /video → load transcript, get status
# /qa    → ask questions, get chat history
app.include_router(video.router, prefix="/video", tags=["Video"])
app.include_router(qa.router,   prefix="/qa",    tags=["Q&A"])

@app.get("/")
def root():
    return {"message": "YouTube Q&A API running. Visit /docs"}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "models_loaded": ModelService.is_ready(),
        "vector_store_ready": vector_store.is_ready(),
    }
