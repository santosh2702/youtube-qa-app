"""
model_service.py — Loads HuggingFace models at startup.

EXACTLY SAME as PDF project.
Same 3 models, same singleton pattern, same classmethod pattern.

Reminder of the 3 models:
  BART     → summarization  (we won't use this in YouTube project
                              since transcripts are already concise)
  MiniLM   → embeddings     (convert text chunks to vectors)
  RoBERTa  → Q&A            (extract answer from context)

NOTE: We drop BART in this project — YouTube transcripts are
already short enough to not need Map-Reduce summarization.
We keep MiniLM and RoBERTa — the RAG pipeline is identical.
"""

from transformers import pipeline
from sentence_transformers import SentenceTransformer


class ModelService:
    _embedder    = None    # MiniLM  — text → vectors
    _qa_pipeline = None    # RoBERTa — context + question → answer
    _ready       = False

    @classmethod
    def load_all(cls):
        print("  Loading embedder (all-MiniLM-L6-v2)...")
        cls._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        print("  Loading QA model (deepset/roberta-base-squad2)...")
        cls._qa_pipeline = pipeline(
            "question-answering",
            model="deepset/roberta-base-squad2",
            device=-1,
        )

        cls._ready = True

    @classmethod
    def get_embedder(cls):
        return cls._embedder

    @classmethod
    def get_qa_pipeline(cls):
        return cls._qa_pipeline

    @classmethod
    def is_ready(cls):
        return cls._ready
