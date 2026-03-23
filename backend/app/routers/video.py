"""
video.py — Router for video loading endpoints.

REPLACES: routers/pdf.py from PDF project

WHAT'S SAME:
  - Same router pattern
  - Same service → router → response flow
  - Same module-level _state dict

WHAT'S NEW:
  - Takes URL not file upload
  - Fetches from YouTube API
  - Stores metadata (title, channel etc)
  - ChromaDB build instead of FAISS build

Endpoints:
  POST /video/load    → load transcript from YouTube URL
  GET  /video/status  → check currently loaded video
  POST /video/clear   → clear history for current video
"""

from fastapi import APIRouter, HTTPException
from app.models.schemas import VideoLoadRequest, VideoLoadResponse, VideoStatusResponse
from app.services.youtube_service import YouTubeService
from app.services.vector_store import vector_store
from app.services.chat_service import ChatService
from app.services.model_service import ModelService

router = APIRouter()

# Module-level state — same pattern as PDF project
_state = {
    "video_id":   None,
    "title":      None,
    "channel":    None,
    "duration":   0,
    "thumbnail":  "",
    "chunk_count": 0,
    "word_count":  0,
}


@router.post("/load", response_model=VideoLoadResponse)
async def load_video(body: VideoLoadRequest):
    """
    Load a YouTube video by URL.

    FLOW:
      1. Extract video ID from URL
      2. Fetch transcript from YouTube API
      3. Fetch video metadata (title, channel etc)
      4. Chunk transcript with timestamps
      5. Build ChromaDB vector index
      6. Return video info to React

    BACKEND TACTIC: URL → ID → API
      We never work with the full URL internally.
      Extract the ID first, use only the ID everywhere.
      IDs are stable and clean — URLs can have extra params.
    """
    if not ModelService.is_ready():
        raise HTTPException(503, "Models still loading. Try again shortly.")

    # Step 1 — extract video ID
    video_id = YouTubeService.extract_video_id(body.url)
    if not video_id:
        raise HTTPException(400, "Invalid YouTube URL. Could not extract video ID.")

    # Step 2 — fetch transcript
    print(f"📺 Fetching transcript for video: {video_id}")
    try:
        transcript = YouTubeService.fetch_transcript(video_id)
    except ValueError as e:
        raise HTTPException(422, str(e))

    # Step 3 — fetch metadata (title, channel, etc)
    print("📋 Fetching video metadata...")
    metadata = YouTubeService.fetch_metadata(video_id)

    # Step 4 — chunk transcript with timestamps
    chunks = YouTubeService.chunk_transcript(transcript, chunk_size=500, overlap=50)
    full_text = YouTubeService.get_full_text(transcript)
    print(f"✂️  Created {len(chunks)} chunks with timestamps")

    # Step 5 — build ChromaDB index
    print("🔢 Building ChromaDB vector index...")
    vector_store.build(chunks, video_id)

    # Step 6 — save state
    _state["video_id"]   = video_id
    _state["title"]      = metadata["title"]
    _state["channel"]    = metadata["channel"]
    _state["duration"]   = metadata["duration"]
    _state["thumbnail"]  = metadata["thumbnail"]
    _state["chunk_count"] = len(chunks)
    _state["word_count"]  = len(full_text.split())

    return VideoLoadResponse(
        message     = "Video loaded and indexed successfully.",
        video_id    = video_id,
        title       = metadata["title"],
        channel     = metadata["channel"],
        duration    = metadata["duration"],
        thumbnail   = metadata["thumbnail"],
        chunk_count = len(chunks),
        word_count  = len(full_text.split()),
    )


@router.get("/status", response_model=VideoStatusResponse)
async def get_status():
    """Check if a video is currently loaded."""
    return VideoStatusResponse(
        loaded      = _state["video_id"] is not None,
        video_id    = _state["video_id"],
        title       = _state["title"],
        channel     = _state["channel"],
        duration    = _state["duration"],
        thumbnail   = _state["thumbnail"],
        chunk_count = _state["chunk_count"],
    )


@router.post("/clear")
async def clear_video():
    """Clear chat history for current video."""
    if _state["video_id"]:
        ChatService.clear_history(_state["video_id"])
    return {"message": "Chat history cleared."}
