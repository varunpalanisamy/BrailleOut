import { useRef, useState } from 'react';
import { BrailleDisplay } from '../components/BrailleDisplay';
import { useWebcam } from '../hooks/useWebcam';
import { useLetterNav } from '../hooks/useLetterNav';
import { parseSentenceToLetters } from '../data/braille';

export function CameraPage() {
  const { videoRef, isReady, error: camError } = useWebcam();
  const [letters, setLetters] = useState<string[]>(['a']); // placeholder
  const [ocrText, setOcrText] = useState('');
  const [processing, setProcessing] = useState(false);
  const [apiError, setApiError] = useState('');
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const nav = useLetterNav(letters);

  const takePhoto = async () => {
    const video = videoRef.current;
    if (!video) return;

    const canvas = canvasRef.current ?? document.createElement('canvas');
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext('2d')?.drawImage(video, 0, 0);
    const imageData = canvas.toDataURL('image/jpeg', 0.85);

    setProcessing(true);
    setApiError('');
    try {
      const res = await fetch('/api/process-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageData }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      const text = data.text || '';
      setOcrText(text);
      const parsed = parseSentenceToLetters(text);
      setLetters(parsed.length ? parsed : ['?']);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setApiError(msg.includes('fetch') ? 'Backend not running — start api_server.py' : msg);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="page-two-col">
      <div className="page-main">
        <div className="section-header">
          <div className="section-title">Camera → Braille</div>
          <div className="section-sub">Point at text, take a picture, and read it in Braille.</div>
        </div>

        {/* Video feed */}
        <div className="camera-wrap">
          <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />

          {!isReady && !camError && (
            <div className="camera-overlay">
              <div className="camera-spinner" />
              <span className="camera-overlay-text">Initializing camera…</span>
            </div>
          )}

          {camError && (
            <div className="camera-overlay">
              <span style={{ fontSize: 28 }}>⚠</span>
              <span className="camera-overlay-text" style={{ color: 'var(--error)' }}>{camError}</span>
            </div>
          )}

          {isReady && (
            <div className="camera-badge">
              <div className="live-dot" />
              LIVE
            </div>
          )}

          <div className="camera-corners">
            <span className="tl" /><span className="tr" />
            <span className="bl" /><span className="br" />
          </div>
        </div>
        <canvas ref={canvasRef} style={{ display: 'none' }} />

        {/* Controls */}
        <button className="capture-btn" onClick={takePhoto} disabled={!isReady || processing}>
          {processing ? 'Processing…' : '📷  Take Picture'}
        </button>

        {/* OCR result */}
        {(ocrText || apiError) && (
          <div className="ocr-result">
            <span className="ocr-label">{apiError ? 'Error' : 'Detected text'}</span>
            <span style={{ color: apiError ? 'var(--error)' : 'inherit' }}>
              {apiError || ocrText || '(no text detected)'}
            </span>
          </div>
        )}
      </div>

      <div className="page-sidebar">
        <BrailleDisplay {...nav} letters={letters} />
      </div>
    </div>
  );
}
