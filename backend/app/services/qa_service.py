"""
qa_service.py — RAG pipeline with timestamp-aware answers.

SAME CONCEPT as PDF project but with 2 upgrades:

  1. TIMESTAMPS in answers
     "The answer is X — mentioned at 2:22 in the video"

  2. CHAT HISTORY aware retrieval
     Uses enriched query (history + question) for ChromaDB search
     Returns better results for follow-up questions
"""

from app.services.vector_store import vector_store
from app.services.chat_service import ChatService
from app.services.model_service import ModelService


class QAService:

    @classmethod
    def answer(cls, question: str, video_id: str, top_k: int = 5) -> dict:
        """
        Full RAG pipeline with chat history and timestamps.

        FLOW:
          1. Enrich query with chat history
          2. ChromaDB retrieves top_k relevant chunks
          3. Build context from chunks
          4. RoBERTa extracts answer
          5. Return answer + timestamp + sources
        """

        # ── STEP 1: ENRICH QUERY ──────────────────────────────────────────────
        # NEW vs PDF project:
        # Use chat history to make the search query smarter
        enriched_query = ChatService.build_enriched_query(video_id, question)

        # ── STEP 2: RETRIEVE ──────────────────────────────────────────────────
        # Search ChromaDB for top_k chunks relevant to enriched query
        # Returns (text, timestamp, score) tuples
        retrieved = vector_store.search(enriched_query, video_id, top_k=top_k)

        if not retrieved:
            return {
                "answer":           "No video loaded or no relevant content found.",
                "timestamp":        "",
                "confidence":       0.0,
                "confidence_label": "low",
                "sources":          [],
            }

        # ── STEP 3: AUGMENT ───────────────────────────────────────────────────
        # Join chunks into context string
        # Same as PDF project
        source_texts = [text for text, timestamp, score in retrieved]
        context = "\n\n---\n\n".join(source_texts)

        # Trim to RoBERTa's limit (~1800 chars ≈ 450 tokens)
        MAX_CONTEXT_CHARS = 1800
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS]

        # ── STEP 4: GENERATE ──────────────────────────────────────────────────
        # Same extractive QA as PDF project
        qa_pipeline = ModelService.get_qa_pipeline()

        result = qa_pipeline(
            question=question,    # original question (not enriched)
            context=context,
            top_k=1,
        )

        answer_text = result["answer"]
        confidence  = round(result["score"], 4)

        # ── STEP 5: FIND TIMESTAMP ────────────────────────────────────────────
        # NEW vs PDF project:
        # The chunk with highest similarity score has the best timestamp
        # That's the most likely place in the video where the answer is
        best_timestamp = retrieved[0][1]   # timestamp of top chunk

        # ── STEP 6: SAVE TO HISTORY ───────────────────────────────────────────
        # NEW vs PDF project:
        # Save this Q&A turn so future questions can use it as context
        ChatService.add_turn(
            video_id=video_id,
            question=question,
            answer=answer_text,
            timestamp=best_timestamp,
            confidence=confidence,
        )

        return {
            "answer":           answer_text,
            "timestamp":        best_timestamp,
            "confidence":       confidence,
            "confidence_label": cls._confidence_label(confidence),
            "sources": [
                {
                    "text":      text[:300] + "..." if len(text) > 300 else text,
                    "timestamp": ts,
                    "score":     round(score, 4),
                }
                for text, ts, score in retrieved
            ],
        }

    @staticmethod
    def _confidence_label(score: float) -> str:
        if score >= 0.7:
            return "high"
        elif score >= 0.3:
            return "medium"
        else:
            return "low"
