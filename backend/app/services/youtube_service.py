"""
youtube_service.py — Fetches transcript from ANY YouTube video.

STRATEGY (2 attempts):
  Attempt 1 — YouTubeTranscriptApi (fast, 2 seconds)
              Works on videos with manual or auto-generated captions.
              Most videos made after 2018 have auto-captions.

  Attempt 2 — yt-dlp + Whisper (slow, 1-5 min on CPU)
              Downloads audio → runs local speech-to-text.
              Works on 100% of videos — no captions needed.
              Same free, local, no API key approach.
"""

import re
import os
import tempfile
import requests
from typing import List, Dict, Optional
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    VideoUnavailable,
)


class YouTubeService:

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'^([0-9A-Za-z_-]{11})$',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def fetch_transcript(video_id: str) -> List[Dict]:
        """
        Fetch transcript using 2-step fallback strategy.

        Step 1: Try YouTubeTranscriptApi (instant)
        Step 2: Download audio + run Whisper (slow but universal)
        """

        # ── ATTEMPT 1: Caption file (fast) ───────────────────────────────────
        print(f"  Attempt 1: Trying YouTube captions API...")
        try:
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=['en', 'en-US', 'en-GB']
            )
            print(f"  ✅ Captions found! {len(transcript)} segments")
            return transcript

        except NoTranscriptFound:
            # Try auto-generated captions
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript = transcript_list.find_generated_transcript(
                    ['en', 'en-US', 'en-GB', 'a.en']
                ).fetch()
                print(f"  ✅ Auto-captions found! {len(transcript)} segments")
                return transcript
            except Exception:
                print("  ❌ No captions available — falling back to Whisper")

        except VideoUnavailable:
            raise ValueError("This video is unavailable (private or deleted).")

        except Exception as e:
            print(f"  ❌ Caption API failed: {e} — falling back to Whisper")

        # ── ATTEMPT 2: yt-dlp + Whisper (universal fallback) ─────────────────
        print(f"  Attempt 2: Downloading audio + running Whisper...")
        print(f"  ⚠️  This may take 1-5 minutes on CPU. Please wait...")
        return YouTubeService._transcribe_with_whisper(video_id)

    @staticmethod
    def _transcribe_with_whisper(video_id: str) -> List[Dict]:
        """
        Download audio from YouTube and transcribe with Whisper locally.

        BACKEND TACTIC: Temp directory for intermediate files
          We download the audio to a temp folder.
          tempfile.TemporaryDirectory() auto-deletes everything
          when the `with` block exits — no cleanup needed.

        BACKEND TACTIC: yt-dlp over pytube
          yt-dlp is maintained actively and never breaks.
          pytube breaks every time YouTube changes their site.
          yt-dlp is the industry standard for YouTube downloads.
        """
        try:
            import yt_dlp
            import whisper
        except ImportError as e:
            raise ValueError(
                f"Missing package: {e}. "
                "Run: pip install yt-dlp openai-whisper"
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = os.path.join(tmp_dir, "audio.mp3")

            # ── Step 1: Download audio only (no video) ────────────────────
            # BACKEND TACTIC: Audio only download
            #   We only need audio for speech-to-text.
            #   Downloading video would be 10x larger — waste of time/disk.
            #   yt-dlp -x flag = extract audio only
            print(f"  Downloading audio for {video_id}...")
            ydl_opts = {
                "format":            "bestaudio/best",
                "outtmpl":           os.path.join(tmp_dir, "audio.%(ext)s"),
                "postprocessors": [{
                    "key":            "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                }],
                "quiet":    True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

            # Find the downloaded audio file
            for f in os.listdir(tmp_dir):
                if f.endswith(".mp3"):
                    audio_path = os.path.join(tmp_dir, f)
                    break

            if not os.path.exists(audio_path):
                raise ValueError("Audio download failed.")

            print(f"  ✅ Audio downloaded: {audio_path}")

            # ── Step 2: Transcribe with Whisper ───────────────────────────
            # BACKEND TACTIC: Whisper model choice
            #   "base" model = good accuracy + reasonable speed on CPU
            #   Takes ~1 min per 10 min of audio on a modern CPU
            #   For faster results: use "tiny" (less accurate)
            #   For better results: use "small" or "medium" (slower)
            print(f"  Running Whisper transcription (base model)...")
            model = whisper.load_model("base")
            result = model.transcribe(
                audio_path,
                # word_timestamps=True gives us per-word timing
                # verbose=False suppresses Whisper's own output
                verbose=False,
                word_timestamps=False,
            )

            # ── Step 3: Convert Whisper output to our format ──────────────
            # Whisper returns: {"segments": [{"text": "...", "start": 0.0, "end": 2.5}]}
            # We need:         [{"text": "...", "start": 0.0, "duration": 2.5}]
            transcript = []
            for segment in result["segments"]:
                transcript.append({
                    "text":     segment["text"].strip(),
                    "start":    segment["start"],
                    "duration": segment["end"] - segment["start"],
                })

            print(f"  ✅ Whisper transcribed {len(transcript)} segments")
            return transcript

    @staticmethod
    def fetch_metadata(video_id: str) -> Dict:
        """
        Fetch video metadata using YouTube oEmbed API.
        No library needed — direct HTTP call. Never breaks.
        """
        try:
            url = (
                f"https://www.youtube.com/oembed"
                f"?url=https://www.youtube.com/watch?v={video_id}"
                f"&format=json"
            )
            res = requests.get(url, timeout=5)
            if res.ok:
                data = res.json()
                return {
                    "title":     data.get("title", "YouTube Video"),
                    "channel":   data.get("author_name", "Unknown"),
                    "duration":  0,
                    "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                    "views":     0,
                }
        except Exception:
            pass

        return {
            "title":     "YouTube Video",
            "channel":   "Unknown",
            "duration":  0,
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            "views":     0,
        }

    @staticmethod
    def chunk_transcript(
        transcript: List[Dict],
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[Dict]:
        """Split transcript into overlapping chunks with timestamps."""
        all_words = []
        for segment in transcript:
            words = segment["text"].split()
            start = segment["start"]
            for word in words:
                all_words.append((word, start))

        chunks = []
        start_idx = 0

        while start_idx < len(all_words):
            end_idx    = min(start_idx + chunk_size, len(all_words))
            chunk_words = all_words[start_idx:end_idx]

            chunk_text       = " ".join(word for word, _ in chunk_words)
            chunk_start_time = chunk_words[0][1]
            chunk_end_time   = chunk_words[-1][1]

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
        seconds = int(seconds)
        hours   = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs    = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    @staticmethod
    def get_full_text(transcript: List[Dict]) -> str:
        return " ".join(segment["text"] for segment in transcript)