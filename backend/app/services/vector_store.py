"""
vector_store.py — ChromaDB persistent vector store.

REPLACES: faiss-based vector_store.py from PDF project

WHAT'S NEW vs PDF project:

  1. PERSISTENCE
     FAISS:    index lives in RAM → lost on restart
     ChromaDB: index saved to disk at ./chroma_db/
               restart server → data still there
               index a video once → available forever

  2. METADATA STORAGE
     FAISS:    stores ONLY vectors (numbers)
               to get the original text, need separate list
     ChromaDB: stores vectors + text + metadata together
               {
                 embedding: [0.12, -0.45, ...],
                 document:  "the actual text chunk",
                 metadata:  {"timestamp": "2:22", "video_id": "abc123"}
               }

  3. MULTI-VIDEO SUPPORT
     FAISS:    one global index — only one PDF at a time
     ChromaDB: filter by video_id → multiple videos stored
               search only within a specific video's chunks

BACKEND TACTIC: ChromaDB Collections
  ChromaDB organizes data into "collections" (like tables in SQL).
  We use ONE collection "youtube_transcripts" for all videos.
  When searching, we filter by video_id to get only that video's chunks.
  This is called "metadata filtering" — very powerful pattern.
"""

import chromadb
import numpy as np
from typing import List, Dict, Tuple, Optional
from app.services.model_service import ModelService


class VectorStore:
    def __init__(self):
        self._client     = None      # ChromaDB client
        self._collection = None      # the collection (like a table)
        self._ready      = False
        self._current_video_id = None

    def init(self):
        """
        Initialize ChromaDB with persistent storage.

        BACKEND TACTIC: PersistentClient vs EphemeralClient
          PersistentClient(path="./chroma_db")
            → saves to disk at that path
            → survives server restarts
            → use in production / real projects

          EphemeralClient()
            → in memory only
            → same as FAISS behavior
            → use for testing only

        We use PersistentClient so the app works like a real product.
        """
        self._client = chromadb.PersistentClient(path="./chroma_db")

        # get_or_create_collection:
        #   if collection exists on disk → reuse it (previous videos still there)
        #   if collection doesn't exist  → create fresh one
        self._collection = self._client.get_or_create_collection(
            name="youtube_transcripts",
            # cosine similarity — same as our normalized FAISS in PDF project
            metadata={"hnsw:space": "cosine"},
        )

        self._ready = True
        print(f"  ChromaDB collection has {self._collection.count()} existing chunks")

    def build(self, chunks: List[Dict], video_id: str) -> None:
        """
        Embed all chunks and store in ChromaDB with metadata.

        WHAT'S NEW vs PDF project:
          - Each chunk stored with video_id and timestamp metadata
          - Unique IDs per chunk (video_id + chunk index)
          - Old chunks for same video deleted before re-indexing

        Args:
            chunks:   list of {text, timestamp, start_time, end_time}
            video_id: YouTube video ID (e.g. "abc123")
        """
        # Delete old chunks for this video if re-indexing
        # BACKEND TACTIC: Idempotency
        #   If user loads the same video twice, we don't want duplicates.
        #   Delete existing chunks for this video_id first.
        try:
            existing = self._collection.get(
                where={"video_id": video_id}
            )
            if existing["ids"]:
                self._collection.delete(where={"video_id": video_id})
                print(f"  Deleted {len(existing['ids'])} old chunks for {video_id}")
        except Exception:
            pass

        # Embed all chunks
        embedder = ModelService.get_embedder()
        texts = [chunk["text"] for chunk in chunks]

        print(f"  Embedding {len(chunks)} chunks...")
        embeddings = embedder.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).tolist()  # ChromaDB needs Python lists, not numpy arrays

        # Build IDs, documents, metadatas, embeddings lists
        # ChromaDB add() takes parallel lists — all same length
        ids         = [f"{video_id}_chunk_{i}" for i in range(len(chunks))]
        documents   = texts
        metadatas   = [
            {
                "video_id":   video_id,
                "timestamp":  chunk["timestamp"],
                "start_time": chunk["start_time"],
                "end_time":   chunk["end_time"],
                "chunk_index": i,
            }
            for i, chunk in enumerate(chunks)
        ]

        # Store everything in ChromaDB
        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        self._current_video_id = video_id
        print(f"  ✅ Stored {len(chunks)} chunks in ChromaDB for video {video_id}")

    def search(
        self,
        query: str,
        video_id: str,
        top_k: int = 5
    ) -> List[Tuple[str, str, float]]:
        """
        Search for relevant chunks within a specific video.

        WHAT'S NEW vs PDF project:
          - Filter by video_id → only search THIS video's chunks
          - Returns (text, timestamp, score) tuples
          - Timestamp tells us WHERE in video the answer is

        Returns:
            List of (chunk_text, timestamp, similarity_score)
        """
        embedder  = ModelService.get_embedder()
        query_vec = embedder.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).tolist()

        # BACKEND TACTIC: Metadata filtering in ChromaDB
        #   where={"video_id": video_id} → only search this video's chunks
        #   Without this, we'd search ALL videos — wrong answers from other videos!
        results = self._collection.query(
            query_embeddings=query_vec,
            n_results=min(top_k, self._collection.count()),
            where={"video_id": video_id},
            include=["documents", "metadatas", "distances"],
        )

        # ChromaDB returns nested lists (supports batch queries)
        # results["documents"][0] → list of documents for first query
        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score: 1 - (distance/2) → 0 to 1
            score = round(1 - (dist / 2), 4)
            output.append((doc, meta["timestamp"], score))

        return output

    def is_ready(self) -> bool:
        return self._ready

    def get_current_video_id(self) -> Optional[str]:
        return self._current_video_id


# Module-level singleton — same pattern as PDF project
vector_store = VectorStore()
