"""
chat_service.py — Manages conversation history.

THIS IS COMPLETELY NEW vs PDF project.

WHAT IT DOES:
  Stores every Q&A turn so the model has context
  for follow-up questions.

  Without this:
    Q: "What does the speaker say about Python?"
    A: "Python is great for beginners..."

    Q: "Why does he prefer it?"      ← "he" and "it" refer to what??
    A: ??? model is lost

  With this:
    Q: "What does the speaker say about Python?"
    A: "Python is great for beginners..."

    [history stored: Q1 + A1]

    Q: "Why does he prefer it?"
    enriched query: "speaker Python prefer beginners Why does he prefer it?"
    A: "Because it has simple syntax and great libraries" ✅

BACKEND TACTIC: Sliding Window History
  We don't use ALL history — just last N turns.
  Why? Too much history = too many tokens for RoBERTa.
  We use last 3 turns = last 3 questions + answers.
  This covers most follow-up patterns without overloading the model.
"""

from typing import List, Dict, Optional
from datetime import datetime


class ChatService:
    # Store history per video_id
    # { "abc123": [ {role, content, timestamp}, ... ] }
    _histories: Dict[str, List[Dict]] = {}

    @classmethod
    def get_history(cls, video_id: str) -> List[Dict]:
        """Get full conversation history for a video."""
        return cls._histories.get(video_id, [])

    @classmethod
    def add_turn(
        cls,
        video_id:  str,
        question:  str,
        answer:    str,
        timestamp: str = "",
        confidence: float = 0.0,
    ) -> None:
        """
        Save one Q&A turn to history.

        BACKEND TACTIC: Structured history entries
          Each entry has a role ("user" or "assistant")
          This matches the format used by OpenAI, LangChain, etc.
          Good habit to use consistent format early.
        """
        if video_id not in cls._histories:
            cls._histories[video_id] = []

        # Add user turn
        cls._histories[video_id].append({
            "role":    "user",
            "content": question,
            "time":    datetime.now().strftime("%H:%M"),
        })

        # Add assistant turn
        cls._histories[video_id].append({
            "role":       "assistant",
            "content":    answer,
            "timestamp":  timestamp,    # where in video
            "confidence": confidence,
            "time":       datetime.now().strftime("%H:%M"),
        })

    @classmethod
    def build_enriched_query(cls, video_id: str, new_question: str) -> str:
        """
        Combine recent history with new question for better retrieval.

        BACKEND TACTIC: Query Enrichment
          The raw question alone might be too short or use pronouns.
          "Why does he prefer it?" → terrible search query
          "speaker Python prefer Why does he prefer it?" → much better

          We take the last 3 Q&A pairs and prepend key words
          to the new question. This gives FAISS/ChromaDB enough
          context to find the right chunks.

          This is called "query rewriting" or "query enrichment"
          and is a standard RAG improvement technique.
        """
        history = cls.get_history(video_id)

        if not history:
            return new_question   # no history yet — use question as-is

        # Get last 3 turns (6 entries: 3 user + 3 assistant)
        recent = history[-6:]

        # Extract text from recent turns
        recent_text = " ".join(
            entry["content"]
            for entry in recent
        )

        # Combine recent context + new question
        # Keep it reasonable length for embedding
        enriched = f"{recent_text} {new_question}"

        # Trim to 500 words max to avoid embedding issues
        words = enriched.split()
        if len(words) > 500:
            enriched = " ".join(words[-500:])

        return enriched

    @classmethod
    def clear_history(cls, video_id: str) -> None:
        """Clear conversation history for a specific video."""
        cls._histories[video_id] = []

    @classmethod
    def get_turn_count(cls, video_id: str) -> int:
        """How many Q&A turns have happened for this video."""
        history = cls._histories.get(video_id, [])
        # divide by 2 because each turn = 1 user + 1 assistant entry
        return len(history) // 2
