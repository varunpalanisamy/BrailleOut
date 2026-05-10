import { useState } from 'react';
import { BrailleDisplay } from '../components/BrailleDisplay';
import { useLetterNav } from '../hooks/useLetterNav';
import { parseSentenceToLetters } from '../data/braille';

type Status = 'idle' | 'loading' | 'ready' | 'error';

function getVideoId(url: string): string | null {
  const m = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
  return m ? m[1] : null;
}

export function YouTubePage() {
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState<Status>('idle');
  const [transcript, setTranscript] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [videoId, setVideoId] = useState('');
  const [letters, setLetters] = useState<string[]>([]);

  const nav = useLetterNav(letters);

  const fetchTranscript = async () => {
    if (!url.trim()) return;
    setStatus('loading');
    setErrorMsg('');
    setTranscript('');
    setLetters([]);

    try {
      const res  = await fetch(`/api/transcript?url=${encodeURIComponent(url)}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      setTranscript(data.text);
      setVideoId(data.video_id ?? getVideoId(url) ?? '');
      setLetters(parseSentenceToLetters(data.text));
      setStatus('ready');
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrorMsg(msg.includes('fetch') ? 'Backend not running — start api_server.py first.' : msg);
      setStatus('error');
    }
  };

  // Build highlighted transcript snippet (first ~500 chars)
  const buildPreview = () => {
    if (!transcript) return null;
    const snippet = transcript.slice(0, 600);
    const chars   = snippet.toLowerCase().split('');
    let li = 0;

    return chars.map((ch, i) => {
      const supported = /[a-z ]/.test(ch);
      if (!supported) return <span key={i} style={{ color: 'var(--text-4)' }}>{transcript[i]}</span>;
      const thisIdx = li++;
      const cur  = thisIdx === nav.currentIndex;
      const past = thisIdx <  nav.currentIndex;
      return (
        <span
          key={i}
          className={cur ? 'cur' : undefined}
          style={past ? { color: 'var(--text-3)' } : undefined}
        >
          {transcript[i]}
        </span>
      );
    });
  };

  return (
    <div className="page-two-col">
      <div className="page-main">
        <div className="section-header">
          <div className="section-title">YouTube → Braille</div>
          <div className="section-sub">Paste a YouTube link to fetch its transcript and read it in Braille.</div>
        </div>

        {/* URL input */}
        <div className="yt-form">
          <input
            className="yt-input"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchTranscript()}
            placeholder="https://www.youtube.com/watch?v=..."
            spellCheck={false}
          />
          <button
            className="action-btn"
            onClick={fetchTranscript}
            disabled={status === 'loading' || !url.trim()}
          >
            {status === 'loading' ? 'Fetching…' : 'Fetch →'}
          </button>
        </div>

        {/* Status chips */}
        {status === 'loading' && (
          <span className="status-chip loading">⟳&nbsp;&nbsp;Fetching transcript…</span>
        )}
        {status === 'error' && (
          <span className="status-chip error-chip">✕&nbsp;&nbsp;{errorMsg}</span>
        )}
        {status === 'ready' && (
          <span className="status-chip success">✓&nbsp;&nbsp;{letters.length} letters loaded</span>
        )}

        {/* Thumbnail */}
        {videoId && (
          <img
            className="yt-thumbnail"
            src={`https://img.youtube.com/vi/${videoId}/hqdefault.jpg`}
            alt="Video thumbnail"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
          />
        )}

        {/* Transcript preview */}
        {transcript && (
          <div className="transcript-box">
            {buildPreview()}
            {transcript.length > 600 && (
              <span style={{ color: 'var(--text-4)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                … ({transcript.length} total chars)
              </span>
            )}
          </div>
        )}

        {/* Backend note / cookie instructions */}
        {status === 'idle' && (
          <div className="card" style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.8 }}>
            <strong style={{ color: 'var(--text-2)', display: 'block', marginBottom: 4 }}>Requirements</strong>
            Run <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--bg-input)', padding: '1px 6px', borderRadius: 4 }}>python api_server.py</code> in the project root before fetching transcripts.
          </div>
        )}
        {status === 'error' && errorMsg.includes('cookies') && (
          <div className="card" style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.8, marginTop: 8 }}>
            <strong style={{ color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>Fix: export your YouTube cookies</strong>
            <ol style={{ paddingLeft: 16, margin: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <li>Install the <strong style={{ color: 'var(--text-2)' }}>Get cookies.txt LOCALLY</strong> Chrome/Firefox extension</li>
              <li>Go to <strong style={{ color: 'var(--text-2)' }}>youtube.com</strong> while logged in</li>
              <li>Click the extension and export cookies for the current site</li>
              <li>Save the file as <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--bg-input)', padding: '1px 5px', borderRadius: 3 }}>cookies.txt</code> in the project root (next to <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--bg-input)', padding: '1px 5px', borderRadius: 3 }}>api_server.py</code>)</li>
              <li>Restart <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--bg-input)', padding: '1px 5px', borderRadius: 3 }}>api_server.py</code> and try again</li>
            </ol>
          </div>
        )}
      </div>

      <div className="page-sidebar">
        {letters.length > 0
          ? <BrailleDisplay {...nav} letters={letters} />
          : (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center', padding: 32, textAlign: 'center' }}>
              <span style={{ fontSize: 32 }}>▷</span>
              <span style={{ color: 'var(--text-3)', fontSize: 13 }}>Fetch a transcript to get started</span>
            </div>
          )
        }
      </div>
    </div>
  );
}
