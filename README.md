# TubeChat — YouTube Q&A AI

Ask any question about any YouTube video. Runs 100% locally. Free. No API keys.

---

## What's New vs PDF Project

| Feature | PDF Project | YouTube Project |
|---|---|---|
| Data source | File upload | YouTube URL |
| Extraction | pdfplumber | YouTubeTranscriptApi |
| Vector store | FAISS (in-memory) | ChromaDB (on-disk) |
| Persistence | Lost on restart | Survives restarts |
| Multi-document | No | Yes (by video_id) |
| Chat history | No | Yes (multi-turn) |
| Timestamps | No | Yes (click to open) |
| Metadata filter | No | Yes (by video_id) |

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React + Vite | UI |
| Backend | Python + FastAPI | REST API |
| Transcript | youtube-transcript-api | Fetch captions |
| Metadata | pytube | Title, channel, duration |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | Text → vectors |
| Q&A | deepset/roberta-base-squad2 | Extract answers |
| Vector DB | ChromaDB | Persistent similarity search |

---

## Project Structure

```
youtube-qa-app/
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py                   ← FastAPI + startup
│       ├── routers/
│       │   ├── video.py              ← POST /video/load, GET /video/status
│       │   └── qa.py                 ← POST /qa/ask, GET /qa/history
│       ├── services/
│       │   ├── model_service.py      ← HuggingFace models (singleton)
│       │   ├── youtube_service.py    ← transcript + metadata + chunking
│       │   ├── vector_store.py       ← ChromaDB (replaces FAISS)
│       │   ├── chat_service.py       ← conversation history (NEW)
│       │   └── qa_service.py         ← RAG pipeline with timestamps
│       └── models/
│           └── schemas.py            ← Pydantic schemas
└── frontend/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx / App.css
        └── components/
            ├── VideoInput.jsx         ← URL input, load video
            ├── VideoInfo.jsx          ← thumbnail, title, stats
            └── ChatWindow.jsx         ← full chat UI with timestamps
```

---

## Setup & Run

### Prerequisites
- Python 3.11
- Node.js 18+

### Backend

```bash
cd youtube-qa-app/backend

python3.11 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

First run downloads ~600MB of models. Cached after that.

Visit **http://localhost:8000/docs** for Swagger UI.

### Frontend

```bash
cd youtube-qa-app/frontend
npm install
npm run dev
```

Open **http://localhost:3000**

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | /video/load | Load YouTube video by URL |
| GET | /video/status | Currently loaded video info |
| POST | /video/clear | Clear chat history |
| POST | /qa/ask | Ask a question |
| GET | /qa/history | Get conversation history |
| POST | /qa/clear | Clear conversation |

---

## New Concepts Explained

### 1. YouTube Transcript API

No scraping, no downloading. YouTube stores captions officially.

```python
from youtube_transcript_api import YouTubeTranscriptApi

transcript = YouTubeTranscriptApi.get_transcript("VIDEO_ID")
# Returns: [{"text": "hello", "start": 0.0, "duration": 2.5}, ...]
```

Each segment has:
- `text` — the spoken words
- `start` — when it was said (in seconds)
- `duration` — how long it lasted

### 2. Timestamp-enriched Chunks

Unlike PDF chunks (plain strings), YouTube chunks carry metadata:

```python
{
  "text":       "gradient descent finds the minimum...",
  "start_time": 142.5,       # seconds into video
  "end_time":   180.0,
  "timestamp":  "2:22"       # human readable
}
```

When the answer is found in this chunk → tell user "see 2:22 in the video".

### 3. ChromaDB vs FAISS

```python
# FAISS — in memory only
index = faiss.IndexFlatIP(384)
index.add(embeddings)
# restart server → everything gone ❌

# ChromaDB — persists to disk
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("youtube_transcripts")
collection.add(documents=chunks, embeddings=embeddings, metadatas=timestamps)
# restart server → data still there ✅
```

### 4. Metadata Filtering

ChromaDB stores metadata alongside vectors. Filter by video_id:

```python
# Only search chunks from THIS video, not all videos
results = collection.query(
    query_embeddings=query_vec,
    where={"video_id": "abc123"},   # ← metadata filter
)
```

FAISS has no metadata — it's just numbers. ChromaDB is richer.

### 5. Chat History & Query Enrichment

```python
# Without history — bad for follow-ups
Q: "What does he say about Python?"
Q: "Why does he prefer it?"   # "it" refers to what?

# With query enrichment
history = "Python great for beginners"
enriched = f"{history} Why does he prefer it?"
# Now ChromaDB finds the right chunks ✅
```

### 6. Optimistic UI Updates

```javascript
// Don't wait for server — add message instantly
setHistory(prev => [...prev, { role: "user", content: question }])

// Then fetch answer in background
const res = await fetch("/qa/ask", ...)

// Add answer when it arrives
setHistory(prev => [...prev, { role: "assistant", content: answer }])
```

Makes the chat feel instant like WhatsApp.

---

## Common Issues

**"No transcript available"**
The video has no captions. Try a video with auto-generated subtitles enabled.

**"Invalid YouTube URL"**
Supported formats:
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://youtube.com/embed/VIDEO_ID`

**ChromaDB errors on first run**
Delete the `./chroma_db/` folder and restart the server.

**Models downloading slowly**
First run downloads ~600MB. After that, models are cached at `~/.cache/huggingface/`.

---

## What to Build Next

```
1. Add streaming responses (answer appears word by word)
2. Persist chat history to SQLite so it survives restarts
3. Support multiple videos simultaneously
4. Add video playlist support (load entire playlist)
5. Export Q&A session as PDF report
```
