import { useState, useEffect } from "react";
import VideoInput from "./components/VideoInput";
import VideoInfo from "./components/VideoInfo";
import ChatWindow from "./components/ChatWindow";
import "./App.css";

export default function App() {
  const [videoStatus, setVideoStatus] = useState(null);
  const [loading, setLoading]         = useState(false);

  // Check if a video is already loaded on mount
  // (ChromaDB persists — video from previous session might still be there)
  useEffect(() => {
    fetch("http://localhost:8000/video/status")
      .then(r => r.json())
      .then(data => { if (data.loaded) setVideoStatus(data); })
      .catch(() => {});
  }, []);

  const handleVideoLoaded = (data) => {
    setVideoStatus(data);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">▶</span>
            <span className="logo-text">TubeChat</span>
          </div>
          <p className="header-sub">Ask anything about any YouTube video · Runs 100% locally</p>
        </div>
      </header>

      <main className="main">
        {/* Left panel — video input + info */}
        <aside className="sidebar">
          <VideoInput
            onLoaded={handleVideoLoaded}
            loading={loading}
            setLoading={setLoading}
          />
          {videoStatus && <VideoInfo status={videoStatus} />}

          {/* How it works box */}
          <div className="how-it-works">
            <p className="how-title">How it works</p>
            <ol>
              <li>Paste any YouTube URL</li>
              <li>Transcript fetched automatically</li>
              <li>Chunked + embedded into ChromaDB</li>
              <li>Ask questions — RAG finds answers</li>
              <li>Timestamps show where in video</li>
            </ol>
          </div>
        </aside>

        {/* Right panel — chat window */}
        <section className="chat-panel">
          {videoStatus ? (
            <ChatWindow videoStatus={videoStatus} />
          ) : (
            <div className="empty-state">
              <span className="empty-icon">▶</span>
              <p className="empty-title">Load a YouTube video to start</p>
              <p className="empty-sub">
                Paste any YouTube URL on the left and click Load Video
              </p>
            </div>
          )}
        </section>
      </main>

      <footer className="footer">
        Powered by <code>all-MiniLM-L6-v2</code> · <code>roberta-base-squad2</code> · ChromaDB · FastAPI
      </footer>
    </div>
  );
}
