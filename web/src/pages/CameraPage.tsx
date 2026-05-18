import { useCallback, useEffect, useRef, useState } from 'react';
import { BrailleDisplay } from '../components/BrailleDisplay';
import { useWebcam } from '../hooks/useWebcam';
import { useLetterNav } from '../hooks/useLetterNav';
import { parseSentenceToLetters } from '../data/braille';

interface CameraOption {
  index: number;
  label: string;
}

type ScanPhase = 'idle' | 'snapping' | 'processing' | 'done' | 'error';
type MicPhase = 'idle' | 'recording' | 'transcribing' | 'done';

export function CameraPage() {
  const { streamUrl } = useWebcam();
  const [letters, setLetters] = useState<string[]>([]);
  const [ocrText, setOcrText] = useState('');
  const [processing, setProcessing] = useState(false);
  const [apiError, setApiError] = useState('');
  const [streamError, setStreamError] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const [isLive, setIsLive] = useState(false);
  const [scanPhase, setScanPhase] = useState<ScanPhase>('idle');
  const [thumbnail, setThumbnail] = useState<string>('');
  const [streamingTokens, setStreamingTokens] = useState('');
  const [gemmaMode, setGemmaMode] = useState<string>('');
  const [suggestedDelay, setSuggestedDelay] = useState<number | undefined>(undefined);
  const lastTextRef = useRef('');

  // Microphone state
  const [micPhase, setMicPhase] = useState<MicPhase>('idle');
  const [audioTranscript, setAudioTranscript] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const autoStopRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [cameras, setCameras] = useState<CameraOption[]>([]);
  const [activeCamera, setActiveCamera] = useState<number | null>(null);
  const [switching, setSwitching] = useState(false);

  const nav = useLetterNav(letters, suggestedDelay);

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

  const captureOnce = useCallback(async (audioTranscriptOverride?: string) => {
    if (processing) return;
    setProcessing(true);
    setApiError('');
    setStreamingTokens('');
    setGemmaMode('');

    try {
      // Step 1: grab frame instantly
      setScanPhase('snapping');
      const snapRes = await fetch('/api/snap', { method: 'POST' });
      const snapData = await snapRes.json();
      if (snapData.error) throw new Error(snapData.error);
      setThumbnail(snapData.thumbnail);

      // Frame captured — user can put the sign down
      setScanPhase('processing');

      // Step 2: stream Gemma inference via SSE
      const txToUse = audioTranscriptOverride ?? audioTranscript;
      const body: Record<string, string> = {};
      if (txToUse) body.audio_transcript = txToUse;

      const gemmaRes = await fetch('/api/gemma-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!gemmaRes.body) throw new Error('No response body from /api/gemma-stream');

      const reader = gemmaRes.body.getReader();
      const decoder = new TextDecoder();
      let sseBuffer = '';
      let finalText = '';
      let finalMode = 'SCENE';
      let finalDelay: number | undefined = undefined;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        sseBuffer += decoder.decode(value, { stream: true });

        const lines = sseBuffer.split('\n');
        sseBuffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (!payload) continue;
          try {
            const evt = JSON.parse(payload);
            if (evt.error) throw new Error(evt.error);
            if (evt.done) {
              finalText = evt.text ?? '';
              finalMode = evt.mode ?? 'SCENE';
              finalDelay = evt.delay ?? undefined;
            } else if (evt.token !== undefined) {
              setStreamingTokens(prev => prev + evt.token);
            }
          } catch (parseErr) {
            if (parseErr instanceof Error && parseErr.message !== 'Unexpected end of JSON input') {
              throw parseErr;
            }
          }
        }
      }

      setOcrText(finalText);
      setGemmaMode(finalMode);
      if (finalDelay !== undefined) setSuggestedDelay(finalDelay);
      setScanPhase('done');

      if (finalText !== lastTextRef.current) {
        lastTextRef.current = finalText;
        const parsed = parseSentenceToLetters(finalText);
        setLetters(parsed.length ? parsed : []);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setApiError(msg.includes('fetch') ? 'Backend not running — start api_server.py' : msg);
      setScanPhase('error');
    } finally {
      setProcessing(false);
    }
  }, [processing, audioTranscript]);

  // Auto-capture loop: fires immediately then every 8s while Live is on
  useEffect(() => {
    if (!isLive) return;
    captureOnce();
    const id = setInterval(captureOnce, 8000);
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

  // ── Microphone handlers ────────────────────────────────────────
  const startMicRecording = useCallback(async () => {
    if (micPhase !== 'idle' || processing) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        if (autoStopRef.current) {
          clearTimeout(autoStopRef.current);
          autoStopRef.current = null;
        }
        setMicPhase('transcribing');
        const blob = new Blob(audioChunksRef.current, { type: mimeType || 'audio/webm' });
        const formData = new FormData();
        formData.append('audio', blob, 'recording.webm');
        try {
          const res = await fetch('/api/transcribe', { method: 'POST', body: formData });
          const data = await res.json();
          const tx: string = data.transcript ?? '';
          setAudioTranscript(tx);
          setMicPhase('done');
          await captureOnce(tx);
        } catch {
          setMicPhase('idle');
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setMicPhase('recording');

      // Auto-stop after 5 seconds
      autoStopRef.current = setTimeout(() => {
        if (mediaRecorderRef.current?.state === 'recording') {
          mediaRecorderRef.current.stop();
        }
      }, 5000);
    } catch {
      setMicPhase('idle');
    }
  }, [micPhase, processing, captureOnce]);

  const stopMicRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const resetMic = useCallback(() => {
    setMicPhase('idle');
    setAudioTranscript('');
  }, []);

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

        {/* Controls row: Live toggle + mic button */}
        <div className="camera-controls-row">
          <button
            className={`capture-btn${isLive ? ' active' : ''}`}
            onClick={() => setIsLive(v => !v)}
            disabled={streamError}
          >
            {isLive ? '⏹ Stop Live' : '▶ Live'}
          </button>

          <button
            className={`mic-btn${micPhase === 'recording' ? ' recording' : ''}`}
            onMouseDown={startMicRecording}
            onMouseUp={stopMicRecording}
            onTouchStart={startMicRecording}
            onTouchEnd={stopMicRecording}
            disabled={processing && micPhase === 'idle'}
            title="Hold to record audio — Gemma will combine speech with camera"
          >
            {micPhase === 'idle' && 'Hold to Speak'}
            {micPhase === 'recording' && 'Recording…'}
            {micPhase === 'transcribing' && 'Transcribing…'}
            {micPhase === 'done' && 'Heard it'}
          </button>
        </div>

        {/* Audio transcript display */}
        {micPhase === 'done' && audioTranscript && (
          <div className="transcript-result">
            <span className="ocr-label">Heard →</span>
            <span>{audioTranscript}</span>
            <button className="transcript-clear" onClick={resetMic} title="Clear transcript">✕</button>
          </div>
        )}

        {/* Status banner */}
        {isLive && (
          <div className="scan-status-banner" data-phase={scanPhase}>
            {scanPhase === 'idle' && (
              <span>Hold text up to camera — scanning starts automatically.</span>
            )}
            {scanPhase === 'snapping' && (
              <span>📸 Capturing frame…</span>
            )}
            {scanPhase === 'processing' && (
              <>
                <span className="scan-spinner" />
                <span>
                  <strong>Frame captured — you can put the sign down.</strong>
                  <br />Gemma 4 is analyzing…
                  {streamingTokens && (
                    <span className="streaming-preview"> {streamingTokens}</span>
                  )}
                </span>
                {thumbnail && (
                  <img
                    src={`data:image/jpeg;base64,${thumbnail}`}
                    alt="Captured frame"
                    className="scan-thumbnail"
                  />
                )}
              </>
            )}
            {scanPhase === 'done' && (
              <span>Done — next scan in a few seconds.</span>
            )}
            {scanPhase === 'error' && (
              <span style={{ color: 'var(--error)' }}>⚠ {apiError}</span>
            )}
          </div>
        )}

        {/* Gemma result with mode badge */}
        {ocrText && (
          <div className="ocr-result">
            <span className="ocr-label">Gemma 4 →</span>
            {gemmaMode && (
              <span className={`ocr-mode-tag mode-${gemmaMode.toLowerCase()}`}>[{gemmaMode}]</span>
            )}
            <span>{ocrText}</span>
          </div>
        )}
      </div>

      <div className="page-sidebar">
        <BrailleDisplay {...nav} letters={letters} />
      </div>
    </div>
  );
}
