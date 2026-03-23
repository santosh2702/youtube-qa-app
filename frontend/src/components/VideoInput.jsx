import { useState } from "react";

export default function VideoInput({ onLoaded, loading, setLoading }) {
  const [url, setUrl]   = useState("");
  const [error, setError] = useState(null);

  const handleLoad = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setError(null);

    try {
      /*
       * FRONTEND TACTIC: JSON body for URL input
       * Unlike PDF upload (FormData), we send the URL as JSON.
       * The backend extracts the video ID from the URL.
       */
      const res = await fetch("http://localhost:8000/video/load", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ url: url.trim() }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to load video");
      }

      const data = await res.json();
      onLoaded(data);
      setUrl("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="input-card">
      <p className="input-card-title">▶ Load YouTube Video</p>

      {error && <div className="alert alert-error">⚠ {error}</div>}

      <input
        className="url-input"
        placeholder="https://youtube.com/watch?v=..."
        value={url}
        onChange={e => setUrl(e.target.value)}
        onKeyDown={e => e.key === "Enter" && !loading && handleLoad()}
        disabled={loading}
      />

      <button
        className="btn btn-primary"
        onClick={handleLoad}
        disabled={loading || !url.trim()}
      >
        {loading ? (
          <><span className="spinner" /> Loading transcript...</>
        ) : (
          "Load Video"
        )}
      </button>

      {loading && (
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 10, fontFamily: "var(--font-mono)" }}>
          Fetching transcript from YouTube...
        </p>
      )}
    </div>
  );
}
