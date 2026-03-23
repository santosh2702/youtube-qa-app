"""
schemas.py — Request/response models for YouTube Q&A API.

SAME CONCEPT as PDF project — Pydantic validates everything automatically.
NEW schemas for video loading and chat history responses.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional


# ── Video Loading ──────────────────────────────────────────────────────────────
class VideoLoadRequest(BaseModel):
    # NEW vs PDF project: URL input instead of file upload
    url: str = Field(
        ...,
        description="YouTube video URL",
        examples=["https://www.youtube.com/watch?v=abc123"],
    )

class VideoLoadResponse(BaseModel):
    message:     str
    video_id:    str
    title:       str
    channel:     str
    duration:    int        # seconds
    thumbnail:   str
    chunk_count: int
    word_count:  int

class VideoStatusResponse(BaseModel):
    loaded:      bool
    video_id:    Optional[str]
    title:       Optional[str]
    channel:     Optional[str]
    duration:    Optional[int]
    thumbnail:   Optional[str]
    chunk_count: int


# ── Q&A ───────────────────────────────────────────────────────────────────────
class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    top_k:    int = Field(default=5, ge=1, le=10)

class SourceChunk(BaseModel):
    text:      str
    timestamp: str     # NEW: "2:22" — where in video
    score:     float

class AnswerResponse(BaseModel):
    answer:           str
    timestamp:        str      # NEW: where in video this answer is from
    confidence:       float
    confidence_label: str
    sources:          List[SourceChunk]


# ── Chat History ───────────────────────────────────────────────────────────────
# NEW vs PDF project — expose chat history to frontend
class ChatEntry(BaseModel):
    role:       str          # "user" or "assistant"
    content:    str
    timestamp:  Optional[str] = ""
    confidence: Optional[float] = 0.0
    time:       Optional[str] = ""

class ChatHistoryResponse(BaseModel):
    video_id:    str
    history:     List[ChatEntry]
    turn_count:  int
