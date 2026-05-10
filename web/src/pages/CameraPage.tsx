import { useState } from 'react';
import { BrailleDisplay } from '../components/BrailleDisplay';
import { useWebcam } from '../hooks/useWebcam';
import { useLetterNav } from '../hooks/useLetterNav';
import { parseSentenceToLetters } from '../data/braille';

export function CameraPage() {
  const { streamUrl } = useWebcam();
  const [letters, setLetters] = useState<string[]>([]);
  const [ocrText, setOcrText] = useState('');
  const [processing, setProcessing] = useState(false);
  const [apiError, setApiError] = useState('');
  const [streamError, setStreamError] = useState(false);

  const nav = useLetterNav(letters);

  const takePhoto = async () => {
    setProcessing(true);
    setApiError('');
    try {
      const res = await fetch('/api/capture', { method: 'POST' });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      const text = data.text || '';
      setOcrText(text);
      const parsed = parseSentenceToLetters(text);
      setLetters(parsed.length ? parsed : []);
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
          <div className="section-sub">Point the webcam at text, capture it, and read it in Braille.</div>
        </div>

        {/* External webcam stream from Flask backend */}
        <div className="camera-wrap">
          {!streamError ? (
            <img
              src={streamUrl}
              alt="Webcam feed"
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onError={() => setStreamError(true)}
            />
          ) : (
            <div className="camera-overlay">
              <span style={{ fontSize: 28 }}>⚠</span>
              <span className="camera-overlay-text" style={{ color: 'var(--error)' }}>
                Cannot reach webcam stream — make sure api_server.py is running
              </span>
            </div>
          )}

          {!streamError && (
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

        {/* Capture button */}
        <button
          className="capture-btn"
          onClick={takePhoto}
          disabled={processing || streamError}
        >
          {processing ? 'Processing…' : '📷  Capture Text'}
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
