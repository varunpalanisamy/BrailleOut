import { RefObject } from 'react';

interface Props {
  videoRef: RefObject<HTMLVideoElement>;
  isReady: boolean;
  error: string | null;
}

export function VideoPanel({ videoRef, isReady, error }: Props) {
  return (
    <div className="video-panel">
      <video ref={videoRef} autoPlay playsInline muted />

      {!isReady && !error && (
        <div className="video-overlay scanning">
          <div className="video-scan-icon" />
          <span className="video-overlay-text">Initializing camera...</span>
        </div>
      )}

      {error && (
        <div className="video-overlay error">
          <div className="video-error-icon">⚠</div>
          <span className="video-error-text">{error}</span>
        </div>
      )}

      {isReady && (
        <div className="video-badge">
          <div className="video-badge-dot" />
          LIVE
        </div>
      )}

      <div className="video-corner tl" />
      <div className="video-corner tr" />
      <div className="video-corner bl" />
      <div className="video-corner br" />
    </div>
  );
}
