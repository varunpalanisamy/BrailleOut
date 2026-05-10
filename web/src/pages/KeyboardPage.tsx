import { useEffect, useRef, useState } from 'react';
import { BrailleDisplay } from '../components/BrailleDisplay';
import { useLetterNav } from '../hooks/useLetterNav';
import { parseSentenceToLetters } from '../data/braille';

export function KeyboardPage() {
  const [input, setInput] = useState('');
  const [letters, setLetters] = useState<string[]>([]);
  const [liveChar, setLiveChar] = useState('');
  const [charFading, setCharFading] = useState(false);
  const prevLive = useRef('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const nav = useLetterNav(letters);

  // Real-time: track last typed char for big display
  const handleInput = (val: string) => {
    setInput(val);
    const last = val.slice(-1);
    if (last && last !== prevLive.current) {
      setCharFading(true);
      setTimeout(() => {
        setLiveChar(last.toLowerCase());
        setCharFading(false);
        prevLive.current = last;
      }, 100);
    }
  };

  // Auto-focus input
  useEffect(() => { inputRef.current?.focus(); }, []);

  const startNav = () => {
    const parsed = parseSentenceToLetters(input);
    setLetters(parsed.length ? parsed : []);
  };

  return (
    <div className="page-two-col">
      <div className="page-main">
        <div className="section-header">
          <div className="section-title">Keyboard → Braille</div>
          <div className="section-sub">Type anything — see the Braille cell update live. Hit Navigate to step through letter by letter.</div>
        </div>

        {/* Live character display */}
        {liveChar && (
          <div className={`live-char-display card${charFading ? ' fading' : ''}`}>
            {liveChar.toUpperCase()}
          </div>
        )}

        {/* Input */}
        <div className="kb-input-area">
          <textarea
            ref={inputRef}
            className="kb-input"
            value={input}
            onChange={(e) => handleInput(e.target.value)}
            placeholder="Start typing…"
            spellCheck={false}
            rows={3}
          />
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              className="action-btn"
              onClick={startNav}
              disabled={!input.trim()}
            >
              Navigate letter by letter →
            </button>
            {letters.length > 0 && (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-3)' }}>
                {letters.length} letter{letters.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="page-sidebar">
        {letters.length > 0
          ? <BrailleDisplay {...nav} letters={letters} />
          : (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center', padding: 32, textAlign: 'center' }}>
              <span style={{ fontSize: 32 }}>⌨</span>
              <span style={{ color: 'var(--text-3)', fontSize: 13 }}>Type something and click Navigate</span>
            </div>
          )
        }
      </div>
    </div>
  );
}
