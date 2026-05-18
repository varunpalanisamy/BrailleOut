import { useCallback, useEffect, useRef, useState } from 'react';
import { BrailleDisplay } from '../components/BrailleDisplay';
import { useWebcam } from '../hooks/useWebcam';
import { useLetterNav } from '../hooks/useLetterNav';
import { parseSentenceToLetters } from '../data/braille';

interface CameraOption { index: number; label: string; }

interface QueueItem {
  id: string;
  thumbnail: string;
  status: 'processing' | 'done' | 'error';
  streamingText: string;
  text: string;
  mode: string;
  letters: string[];
}

const MAX_QUEUE = 5;
const MAX_CONCURRENT = 2;
const SNAP_INTERVAL_MS = 5000;
const BACKEND = 'http://localhost:5001';

const FALLBACK_PHRASES = new Set(['text visible', 'scene ahead', 'person present', 'nothing detected']);

function isSimilar(a: string, b: string): boolean {
  if (!a || !b) return false;
  if (FALLBACK_PHRASES.has(a) && FALLBACK_PHRASES.has(b)) return a === b;
  if (FALLBACK_PHRASES.has(a) || FALLBACK_PHRASES.has(b)) return false;
  const wa = new Set(a.toLowerCase().split(/\s+/).filter(Boolean));
  const wb = new Set(b.toLowerCase().split(/\s+/).filter(Boolean));
  if (wa.size === 0 || wb.size === 0) return false;
  const intersection = [...wa].filter(w => wb.has(w)).length;
  const jaccard = intersection / new Set([...wa, ...wb]).size;
  const subsetRatio = Math.max(intersection / wa.size, intersection / wb.size);
  return (jaccard >= 0.65 || (subsetRatio >= 0.8 && Math.min(wa.size, wb.size) >= 2))
    && intersection >= 2;
}

export function CameraPage() {
  const { streamUrl } = useWebcam();
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [letters, setLetters] = useState<string[]>([]);
  const [isLive, setIsLive] = useState(false);
  const [streamError, setStreamError] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const [cameras, setCameras] = useState<CameraOption[]>([]);
  const [activeCamera, setActiveCamera] = useState<number | null>(null);
  const [switching, setSwitching] = useState(false);
  const [suggestedDelay, setSuggestedDelay] = useState<number | undefined>(undefined);

  const queueRef = useRef<QueueItem[]>([]);
  queueRef.current = queue;

  const nav = useLetterNav(letters, suggestedDelay);

  // Auto-retry stream every 3s when in error state
  useEffect(() => {
    if (!streamError) return;
    const id = setInterval(() => {
      setStreamError(false);
      setStreamKey(k => k + 1);
    }, 3000);
    return () => clearInterval(id);
  }, [streamError]);

  // Keep auto-advance running as new letters arrive
  useEffect(() => {
    if (isLive && letters.length > 0 && !nav.isAuto) nav.startAuto();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [letters.length, isLive]);

  useEffect(() => {
    fetch('/api/cameras')
      .then(r => r.json())
      .then(d => { setCameras(d.cameras ?? []); setActiveCamera(d.active ?? null); })
      .catch(() => {});
  }, []);

  const switchCamera = async (index: number) => {
    if (index === activeCamera || switching) return;
    setSwitching(true);
    try {
      const d = await fetch('/api/set-camera', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index }),
      }).then(r => r.json());
      if (d.ok) { setActiveCamera(d.active); setStreamError(false); setStreamKey(k => k + 1); }
    } catch { /* backend offline */ } finally { setSwitching(false); }
  };

  // ── Process one queue item via SSE ──────────────────────────────
  const processItem = useCallback(async (id: string, imageb64: string) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      const res = await fetch(`${BACKEND}/api/gemma-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_b64: imageb64 }),
        signal: controller.signal,
      });
      if (!res.body) throw new Error('no body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (!payload) continue;
          try {
            const evt = JSON.parse(payload);
            if (evt.token !== undefined) {
              setQueue(prev => prev.map(item =>
                item.id === id ? { ...item, streamingText: item.streamingText + evt.token } : item
              ));
            }
            if (evt.done) {
              if (evt.delay !== undefined) setSuggestedDelay(evt.delay);
              const newText: string = evt.text ?? '';
              const parsedLetters = parseSentenceToLetters(newText);

              if (FALLBACK_PHRASES.has(newText)) {
                setQueue(prev => prev.filter(i => i.id !== id));
                return;
              }

              const currentQueue = queueRef.current;
              const prevDone = currentQueue.filter(i => i.status === 'done' && i.id !== id);
              const lastDone = prevDone[prevDone.length - 1];
              const isDuplicate = !!(lastDone && isSimilar(lastDone.text, newText));

              if (isDuplicate) {
                setQueue(prev => prev.filter(i => i.id !== id));
              } else {
                setQueue(prev => prev.map(item =>
                  item.id === id
                    ? { ...item, status: 'done', text: newText, mode: evt.mode ?? '', letters: parsedLetters, streamingText: '' }
                    : item
                ));
                setLetters(l => [...l, ...parsedLetters]);
              }
            }
          } catch { /* ignore malformed SSE */ }
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        setQueue(prev => prev.filter(i => i.id !== id));
      } else {
        setQueue(prev => prev.map(item =>
          item.id === id ? { ...item, status: 'error', streamingText: '' } : item
        ));
      }
    } finally {
      clearTimeout(timeout);
    }
  }, []);

  // ── Snap one frame, add to queue, fire Gemma in background ──────
  const snapAndQueue = useCallback(async () => {
    const inFlight = queueRef.current.filter(i => i.status === 'processing').length;
    if (inFlight >= MAX_CONCURRENT) return;
    let thumbnail = '';
    try {
      const d = await fetch('/api/snap', { method: 'POST' }).then(r => r.json());
      if (!d.thumbnail) return;
      thumbnail = d.thumbnail;
    } catch { return; }

    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setQueue(prev => [
      ...prev,
      { id, thumbnail, status: 'processing', streamingText: '', text: '', mode: '', letters: [] },
    ].slice(-MAX_QUEUE));

    processItem(id, thumbnail);
  }, [processItem]);

  // ── Live mode ────────────────────────────────────────────────────
  useEffect(() => {
    if (!isLive) return;
    snapAndQueue();
    const snapId = setInterval(snapAndQueue, SNAP_INTERVAL_MS);
    return () => clearInterval(snapId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLive]);

  const stopLive = () => {
    setIsLive(false);
    setQueue([]);
    setLetters([]);
    nav.stopAuto();
  };

  const processingCount = queue.filter(i => i.status === 'processing').length;
  const doneCount = queue.filter(i => i.status === 'done').length;

  return (
    <div className="page-two-col">
      <div className="page-main">

        <div className="camera-panel">
          <div className="section-header">
            <div className="section-title">Camera → Braille</div>
            <div className="section-sub">
              Live mode snaps every {SNAP_INTERVAL_MS / 1000}s — duplicate scenes are discarded automatically.
            </div>
          </div>

          {cameras.length > 0 && (
            <div className="camera-selector">
              <span className="camera-selector-label">Camera</span>
              <div className="camera-selector-btns">
                {cameras.map(cam => (
                  <button key={cam.index}
                    className={`camera-sel-btn${cam.index === activeCamera ? ' active' : ''}`}
                    onClick={() => switchCamera(cam.index)} disabled={switching}
                  >{cam.label}</button>
                ))}
              </div>
            </div>
          )}

          <div className="camera-wrap">
            {!streamError ? (
              <img key={streamKey} src={streamUrl} alt="Webcam feed"
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                onError={() => setStreamError(true)} />
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
                {isLive
                  ? `SCANNING${processingCount > 0 ? ` · ${processingCount} pending` : ''}`
                  : 'LIVE'}
              </div>
            )}
            <div className="camera-corners">
              <span className="tl" /><span className="tr" />
              <span className="bl" /><span className="br" />
            </div>
          </div>

          <button
            className={`capture-btn${isLive ? ' active' : ''}`}
            onClick={() => isLive ? stopLive() : setIsLive(true)}
            disabled={streamError}
            style={{ width: '100%' }}
          >
            {isLive ? '⏹ Stop' : '▶ Live'}
          </button>
        </div>

        {queue.length > 0 && (
          <div className="gemma-queue">
            <div className="gemma-queue-header">
              <span className="gemma-queue-title">Analysis Queue</span>
              {doneCount > 0 && (
                <span className="gemma-queue-stats">{doneCount} done{processingCount > 0 ? ` · ${processingCount} pending` : ''}</span>
              )}
            </div>
            <div className="gemma-queue-list">
              {[...queue].reverse().map(item => (
                <div key={item.id} className={`gemma-queue-card status-${item.status}`}>
                  <img src={`data:image/jpeg;base64,${item.thumbnail}`} alt="" className="gemma-queue-thumb" />
                  <div className="gemma-queue-body">
                    {item.status === 'processing' && (
                      <div className="gemma-queue-pending">
                        <span className="scan-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                        <span className="gemma-queue-streaming">
                          {item.streamingText || 'Analyzing…'}
                        </span>
                      </div>
                    )}
                    {item.status === 'done' && (
                      <>
                        <div className="gemma-queue-meta">
                          {item.mode && <span className={`ocr-mode-tag mode-${item.mode.toLowerCase()}`}>{item.mode}</span>}
                        </div>
                        <div className="gemma-queue-text">{item.text}</div>
                      </>
                    )}
                    {item.status === 'error' && <span className="gemma-queue-error">Analysis failed</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="page-sidebar">
        <BrailleDisplay {...nav} letters={letters} />
      </div>
    </div>
  );
}
