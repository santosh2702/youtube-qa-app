"""
youtube_service.py — Fetches transcript and metadata from YouTube.

REPLACES: pdf_service.py from the PDF project

WHAT'S NEW:
  - No file upload — just a URL
  - YouTubeTranscriptApi fetches captions automatically
  - Transcript comes with TIMESTAMPS per segment
  - We preserve timestamps through chunking
  - Video metadata (title, channel, duration) via pytube

BACKEND TACTIC: External API Integration
  Instead of reading a local file (pdfplumber),
  we call an external service (YouTube's caption API).
  Key differences:
    - Can fail due to network issues → need better error handling
    - Video might have no captions → handle gracefully
    - Video might be private → handle gracefully
    - Rate limiting possible → retry logic in production

HOW YouTube TRANSCRIPT API WORKS:
  YouTube stores captions as timed text files (XML).
  YouTubeTranscriptApi fetches and parses these files.
  Returns a list of segments:
  [
    {"text": "hello everyone",  "start": 0.0,  "duration": 2.5},
    {"text": "today we learn",  "start": 2.5,  "duration": 1.8},
    ...
  ]
  No scraping, no downloads — YouTube provides these officially.
"""

import re
from typing import List, Dict, Optional
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, VideoUnavailable
from pytube import YouTube


class YouTubeService:

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """
        Extract the video ID from any YouTube URL format.

        BACKEND TACTIC: Regex for URL parsing
          YouTube URLs come in many formats:
            https://www.youtube.com/watch?v=abc123
            https://youtu.be/abc123
            https://youtube.com/embed/abc123
            https://www.youtube.com/watch?v=abc123&t=30s
          We use regex to handle ALL formats in one pattern.
        """
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',   # standard and shortened
            r'(?:embed\/)([0-9A-Za-z_-]{11})',     # embed URLs
            r'^([0-9A-Za-z_-]{11})$',              # just the ID itself
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    @staticmethod
    def fetch_transcript(video_id: str) -> List[Dict]:
        """
        Fetch the full transcript from YouTube with timestamps.

        Returns list of segments:
        [
            {"text": "...", "start": 0.0, "duration": 2.5},
            ...
        ]

        BACKEND TACTIC: Specific Exception Handling
          Always catch SPECIFIC exceptions, not just `except Exception`.
          - NoTranscriptFound → video exists but has no captions
          - VideoUnavailable  → video is private or deleted
          - Generic Exception → network issues, unexpected errors
          Each gives a different, helpful error message to the user.
        """
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            return transcript
        except NoTranscriptFound:
            raise ValueError(
                "This video has no captions/transcript available. "
                "Try a video with auto-generated or manual captions."
            )
        except VideoUnavailable:
            raise ValueError(
                "This video is unavailable (private or deleted)."
            )
        except Exception as e:
            raise ValueError(f"Failed to fetch transcript: {str(e)}")

    @staticmethod
    def fetch_metadata(video_id: str) -> Dict:
        """
        Fetch video metadata: title, channel, duration, thumbnail.

        BACKEND TACTIC: Graceful degradation
          If metadata fetch fails (pytube can be flaky),
          we return default values instead of crashing.
          The transcript is what matters — metadata is just nice to have.
        """
        try:
            yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
            return {
                "title":      yt.title or "Unknown Title",
                "channel":    yt.author or "Unknown Channel",
                "duration":   yt.length or 0,            # in seconds
                "thumbnail":  yt.thumbnail_url or "",
                "views":      yt.views or 0,
            }
        except Exception:
            # metadata is optional — don't crash if pytube fails
            return {
                "title":     "YouTube Video",
                "channel":   "Unknown",
                "duration":  0,
                "thumbnail": "",
                "views":     0,
            }

    @staticmethod
    def chunk_transcript(
        transcript: List[Dict],
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[Dict]:
        """
        Split transcript into overlapping chunks WITH timestamps.

        WHAT'S NEW vs PDF project:
          PDF chunks were plain strings: ["text text text..."]
          YouTube chunks are dicts with timestamp metadata:
          [
            {
              "text":       "text text text...",
              "start_time": 142.5,       ← seconds into video
              "timestamp":  "2:22",      ← human readable
              "end_time":   180.0,
            },
            ...
          ]

        WHY KEEP TIMESTAMPS?
          When RoBERTa finds the answer in chunk 3,
          we know chunk 3 starts at 2:22 in the video.
          We can tell the user: "Find this at 2:22" ← great UX!

        BACKEND TACTIC: Metadata-enriched chunks
          Always store useful metadata alongside your text chunks.
          ChromaDB (unlike FAISS) supports this natively.
          Later when you retrieve a chunk, you get the text AND
          the timestamp — no need to look it up separately.
        """

        # Step 1 — join all transcript segments into one big text
        # but track which word started at which timestamp
        all_words = []    # list of (word, start_time)

        for segment in transcript:
            words = segment["text"].split()
            start = segment["start"]
            for word in words:
                all_words.append((word, start))

        # Step 2 — chunk with overlap, same logic as PDF project
        # but now each chunk knows its start timestamp
        chunks = []
        start_idx = 0

        while start_idx < len(all_words):
            end_idx = min(start_idx + chunk_size, len(all_words))

            # get words and their timestamps for this chunk
            chunk_words = all_words[start_idx:end_idx]

            chunk_text       = " ".join(word for word, _ in chunk_words)
            chunk_start_time = chunk_words[0][1]    # timestamp of first word
            chunk_end_time   = chunk_words[-1][1]   # timestamp of last word

            chunks.append({
                "text":       chunk_text,
                "start_time": chunk_start_time,
                "end_time":   chunk_end_time,
                "timestamp":  YouTubeService.format_timestamp(chunk_start_time),
            })

            start_idx += chunk_size - overlap

        return chunks

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """
        Convert seconds to human readable timestamp.

        142.5 seconds → "2:22"
        3661  seconds → "1:01:01"
        """
        seconds = int(seconds)
        hours   = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs    = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    @staticmethod
    def get_full_text(transcript: List[Dict]) -> str:
        """Join all transcript segments into one plain text string."""
        return " ".join(segment["text"] for segment in transcript)
