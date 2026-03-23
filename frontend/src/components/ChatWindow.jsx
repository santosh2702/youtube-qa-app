import { useState, useEffect, useRef } from "react";

const SUGGESTIONS = [
  "What is this video about?",
  "What are the key points?",
  "Who is speaking in this video?",
  "Summarize the main argument",
];

export default function ChatWindow({ videoStatus }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory]   = useState([]);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const [openSources, setOpenSources] = useState({});
  const bottomRef = useRef(null);

  // Load existing chat history when video changes
  // FRONTEND TACTIC: Fetch history on mount
  // ChromaDB persists vectors but chat history lives in Python memory.
  // On page refresh, history is gone — but vectors stay.
  // In a production app, you'd persist history to a database too.
  useEffect(() => {
    if (!videoStatus?.video_id) return;
    fetch("http://localhost:8000/qa/history")
      .then(r => r.json())
      .then(data => setHistory(data.history || []))
      .catch(() => {});
  }, [videoStatus?.video_id]);

  // Auto-scroll to bottom when new message arrives
  // FRONTEND TACTIC: useRef for DOM access
  // We need direct DOM access to scroll — useRef gives us that
  // without triggering re-renders like useState would.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, loading]);

  const ask = async (q) => {
    const trimmed = (q || question).trim();
    if (!trimmed || loading) return;

    // Optimistically add user message to UI immediately
    // FRONTEND TACTIC: Optimistic updates
    // Don't wait for server — add user message instantly.
    // Makes the app feel fast and responsive like WhatsApp.
    setHistory(prev => [...prev, {
      role:    "user",
      content: trimmed,
      time:    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    }]);
    setQuestion("");
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("http://localhost:8000/qa/ask", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ question: trimmed, top_k: 5 }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to get answer");
      }

      const data = await res.json();

      // Add assistant response to history
      setHistory(prev => [...prev, {
        role:             "assistant",
        content:          data.answer,
        timestamp:        data.timestamp,
        confidence:       data.confidence,
        confidence_label: data.confidence_label,
        sources:          data.sources,
        time:             new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      }]);

    } catch (e) {
      setError(e.message);
      // Remove the optimistic user message on error
      setHistory(prev => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  const clearHistory = async () => {
    await fetch("http://localhost:8000/qa/clear", { method: "POST" });
    setHistory([]);
  };

  const toggleSources = (i) =>
    setOpenSources(prev => ({ ...prev, [i]: !prev[i] }));

  // Open video at specific timestamp
  // FRONTEND TACTIC: YouTube timestamp URL
  // YouTube supports ?t=142 to start at 2:22
  // We convert "2:22" back to seconds for the URL
  const openAtTimestamp = (videoId, timestamp) => {
    const parts  = timestamp.split(":").map(Number);
    let seconds  = 0;
    if (parts.length === 2) seconds = parts[0] * 60 + parts[1];
    if (parts.length === 3) seconds = parts[0] * 3600 + parts[1] * 60 + parts[2];
    window.open(
      `https://www.youtube.com/watch?v=${videoId}&t=${seconds}`,
      "_blank"
    );
  };

  return (
    <>
      {/* Chat header */}
      <div className="chat-header">
        <div>
          <p className="chat-title">Chat with this video</p>
          <p className="chat-subtitle">
            {history.filter(h => h.role === "user").length} questions asked
          </p>
        </div>
        {history.length > 0 && (
          <button className="btn-ghost" onClick={clearHistory}>
            Clear chat
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {history.length === 0 && !loading && (
          <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--text-muted)" }}>
            <p style={{ fontSize: 14 }}>Ask your first question about this video</p>
          </div>
        )}

        {history.map((msg, i) => (
          <div
            key={i}
            className={`msg ${msg.role === "user" ? "msg-user" : "msg-assistant"}`}
          >
            <div className="msg-bubble">{msg.content}</div>

            {/* Assistant message metadata */}
            {msg.role === "assistant" && (
              <>
                <div className="msg-meta">
                  {/* Timestamp badge — click to open video at that point */}
                  {msg.timestamp && (
                    <span
                      className="timestamp-badge"
                      onClick={() => openAtTimestamp(videoStatus.video_id, msg.timestamp)}
                      title="Click to open video at this timestamp"
                    >
                      ▶ {msg.timestamp}
                    </span>
                  )}

                  {/* Confidence indicator */}
                  {msg.confidence > 0 && (
                    <>
                      <span className={`conf-dot conf-${msg.confidence_label}`} />
                      <span>{(msg.confidence * 100).toFixed(0)}% confidence</span>
                    </>
                  )}

                  <span>{msg.time}</span>
                </div>

                {/* Source chunks toggle */}
                {msg.sources?.length > 0 && (
                  <>
                    <button
                      className="sources-toggle"
                      onClick={() => toggleSources(i)}
                    >
                      {openSources[i] ? "▲ Hide" : "▼ Show"} {msg.sources.length} sources
                    </button>

                    {openSources[i] && (
                      <div className="sources-list">
                        {msg.sources.map((src, j) => (
                          <div key={j} className="source-item">
                            <span
                              className="source-ts"
                              style={{ cursor: "pointer" }}
                              onClick={() => openAtTimestamp(videoStatus.video_id, src.timestamp)}
                              title="Open at this timestamp"
                            >
                              ▶ {src.timestamp}
                            </span>
                            score: {(src.score * 100).toFixed(0)}%
                            <br />
                            {src.text}
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </>
            )}

            {/* User message time */}
            {msg.role === "user" && (
              <div className="msg-meta" style={{ justifyContent: "flex-end" }}>
                <span>{msg.time}</span>
              </div>
            )}
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="msg msg-assistant">
            <div className="msg-bubble" style={{ color: "var(--text-muted)" }}>
              <span className="spinner" style={{
                borderColor: "var(--border)",
                borderTopColor: "var(--accent)",
                marginRight: 8
              }} />
              Searching transcript...
            </div>
          </div>
        )}

        {error && (
          <div className="alert alert-error">⚠ {error}</div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Suggested questions — show only when no history */}
      {history.length === 0 && (
        <div className="suggestions">
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              className="suggestion-btn"
              onClick={() => ask(s)}
              disabled={loading}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="chat-input-row">
        <input
          className="chat-input"
          placeholder="Ask anything about this video..."
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !loading && ask()}
          disabled={loading}
        />
        <button
          className="send-btn"
          onClick={() => ask()}
          disabled={loading || !question.trim()}
        >
          {loading ? <span className="spinner" style={{ width: 14, height: 14 }} /> : "↑"}
        </button>
      </div>
    </>
  );
}
