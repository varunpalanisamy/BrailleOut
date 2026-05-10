import { useCallback, useEffect, useRef, useState } from 'react';
import { BrailleDisplay } from '../components/BrailleDisplay';
import { useWebcam } from '../hooks/useWebcam';
import { useLetterNav } from '../hooks/useLetterNav';
import { parseSentenceToLetters } from '../data/braille';

interface CameraOption {
  index: number;
  label: string;
}

export function CameraPage() {
  const { streamUrl } = useWebcam();
  const [letters, setLetters] = useState<string[]>([]);
  const [ocrText, setOcrText] = useState('');
  const [processing, setProcessing] = useState(false);
  const [apiError, setApiError] = useState('');
  const [streamError, setStreamError] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const [isLive, setIsLive] = useState(false);
  const lastTextRef = useRef('');

  const [cameras, setCameras] = useState<CameraOption[]>([]);
  const [activeCamera, setActiveCamera] = useState<number | null>(null);
  const [switching, setSwitching] = useState(false);

  const nav = useLetterNav(letters);

  useEffect(() => {
    fetch('/api/cameras')
      .then(r => r.json())
      .then(data => {
        setCameras(data.cameras ?? []);
        setActiveCamera(data.active ?? null);
      })
      .catch(() => {});
  }, []);

  const switchCamera = async (index: number) => {
    if (index === activeCamera || switching) return;
    setSwitching(true);
    try {
      const res = await fetch('/api/set-camera', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index }),
      });
      const data = await res.json();
      if (data.ok) {
        setActiveCamera(data.active);
        setStreamError(false);
        setStreamKey(k => k + 1);
      }
    } catch {
      // backend not running
    } finally {
      setSwitching(false);
    }
  };

  const captureOnce = useCallback(async () => {
    if (processing) return;
    setProcessing(true);
    setApiError('');
    try {
      const res = await fetch('/api/capture', { method: 'POST' });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      const text = data.text || '';
      setOcrText(text);
      if (text !== lastTextRef.current) {
        lastTextRef.current = text;
        const parsed = parseSentenceToLetters(text);
        setLetters(parsed.length ? parsed : []);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setApiError(msg.includes('fetch') ? 'Backend not running — start api_server.py' : msg);
    } finally {
      setProcessing(false);
    }
  }, [processing]);

  // Auto-capture loop: fires immediately then every 2500 ms while Live is on
  useEffect(() => {
    if (!isLive) return;
    captureOnce();
    const id = setInterval(captureOnce, 2500);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLive]);

  // When Live mode loads new letters, start Braille auto-advance immediately
  useEffect(() => {
    if (isLive && letters.length > 1) {
      nav.startAuto();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [letters]);

  return (
    <div className="page-two-col">
      <div className="page-main">
        <div className="section-header">
          <div className="section-title">Camera → Braille</div>
          <div className="section-sub">Toggle Live, point the webcam at text, and watch it load into the Braille display automatically.</div>
        </div>

        {/* Camera selector */}
        {cameras.length > 0 && (
          <div className="camera-selector">
            <span className="camera-selector-label">Camera</span>
            <div className="camera-selector-btns">
              {cameras.map(cam => (
                <button
                  key={cam.index}
                  className={`camera-sel-btn${cam.index === activeCamera ? ' active' : ''}`}
                  onClick={() => switchCamera(cam.index)}
                  disabled={switching}
                >
                  {cam.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* External webcam stream from Flask backend */}
        <div className="camera-wrap">
          {!streamError ? (
            <img
              key={streamKey}
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
              <div className={`live-dot${isLive ? '' : ' inactive'}`} />
              {isLive ? 'SCANNING' : 'LIVE'}
            </div>
          )}

          <div className="camera-corners">
            <span className="tl" /><span className="tr" />
            <span className="bl" /><span className="br" />
          </div>
        </div>

        {/* Live toggle */}
        <button
          className={`capture-btn${isLive ? ' active' : ''}`}
          onClick={() => setIsLive(v => !v)}
          disabled={streamError}
        >
          {isLive
            ? (processing ? '⏳ Scanning…' : '⏹ Stop Live')
            : '▶ Live'}
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
