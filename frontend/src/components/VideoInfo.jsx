function formatDuration(seconds) {
  if (!seconds) return "Unknown";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${s}s`;
}

export default function VideoInfo({ status }) {
  if (!status?.loaded) return null;

  return (
    <div className="video-card">
      {status.thumbnail ? (
        <img className="video-thumbnail" src={status.thumbnail} alt={status.title} />
      ) : (
        <div className="video-thumbnail-placeholder">▶</div>
      )}

      <div className="video-meta">
        <p className="video-title">{status.title}</p>
        <p className="video-channel">{status.channel}</p>
        <div className="video-stats">
          <span className="stat-badge">⏱ {formatDuration(status.duration)}</span>
          <span className="stat-badge">✂ {status.chunk_count} chunks</span>
          <span className="stat-badge">📝 {status.word_count?.toLocaleString()} words</span>
        </div>
      </div>
    </div>
  );
}
