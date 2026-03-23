"""
qa.py — Router for Q&A and chat history endpoints.

SAME CONCEPT as PDF project qa.py but with:
  - video_id awareness (which video are we asking about?)
  - chat history endpoint (new)
  - timestamp in response (new)

Endpoints:
  POST /qa/ask         → ask a question about loaded video
  GET  /qa/history     → get full conversation history
  POST /qa/clear       → clear conversation history
"""

from fastapi import APIRouter, HTTPException
from app.models.schemas import QuestionRequest, AnswerResponse, ChatHistoryResponse
from app.services.qa_service import QAService
from app.services.chat_service import ChatService
from app.services.vector_store import vector_store
from app.services.model_service import ModelService

router = APIRouter()


@router.post("/ask", response_model=AnswerResponse)
async def ask_question(body: QuestionRequest):
    """
    Ask a question about the currently loaded YouTube video.

    NEW vs PDF project:
      - Gets video_id from vector_store (knows current video)
      - Returns timestamp showing WHERE in video answer is found
      - Chat history automatically saved by QAService
    """
    if not ModelService.is_ready():
        raise HTTPException(503, "Models still loading.")

    video_id = vector_store.get_current_video_id()
    if not video_id:
        raise HTTPException(400, "No video loaded. Please load a YouTube video first.")

    result = QAService.answer(
        question=body.question,
        video_id=video_id,
        top_k=body.top_k,
    )

    return AnswerResponse(**result)


@router.get("/history", response_model=ChatHistoryResponse)
async def get_history():
    """
    Get the full conversation history for current video.

    NEW vs PDF project — completely new endpoint.
    Frontend calls this to display the chat window.
    """
    video_id = vector_store.get_current_video_id()
    if not video_id:
        raise HTTPException(400, "No video loaded.")

    history    = ChatService.get_history(video_id)
    turn_count = ChatService.get_turn_count(video_id)

    return ChatHistoryResponse(
        video_id   = video_id,
        history    = history,
        turn_count = turn_count,
    )


@router.post("/clear")
async def clear_history():
    """Clear conversation history for current video."""
    video_id = vector_store.get_current_video_id()
    if video_id:
        ChatService.clear_history(video_id)
    return {"message": "Conversation history cleared."}
