import { useState } from 'react';
import { BrailleDisplay } from '../components/BrailleDisplay';
import { useLetterNav } from '../hooks/useLetterNav';
import { parseSentenceToLetters } from '../data/braille';

export function TextPage() {
  const [input, setInput] = useState('');
  const [letters, setLetters] = useState<string[]>([]);

  const nav = useLetterNav(letters);

  const convert = () => {
    const parsed = parseSentenceToLetters(input);
    setLetters(parsed);
  };

  // Build highlighted preview
  const buildPreview = () => {
    if (!letters.length) return null;
    const chars = input.toLowerCase().split('');
    let letterIdx = 0;

    return chars.map((ch, i) => {
      const isSupported = /[a-z ]/.test(ch);
      if (!isSupported) return <span key={i} style={{ color: 'var(--text-4)' }}>{ch}</span>;

      const thisIdx = letterIdx;
      letterIdx++;
      const isCurrent = thisIdx === nav.currentIndex;
      const isPast    = thisIdx < nav.currentIndex;

      return (
        <span
          key={i}
          className={isCurrent ? 'current-char' : undefined}
          style={isPast ? { color: 'var(--text-3)' } : undefined}
        >
          {ch === ' ' ? ' ' : ch}
        </span>
      );
    });
  };

  return (
    <div className="page-two-col">
      <div className="page-main">
        <div className="section-header">
          <div className="section-title">Text → Braille</div>
          <div className="section-sub">Paste a news article, a sentence, or any text to navigate it in Braille.</div>
        </div>

        <textarea
          className="text-area"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Paste or type text here…&#10;&#10;Try a news headline, article excerpt, or any paragraph."
          spellCheck={false}
        />

        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button className="action-btn" onClick={convert} disabled={!input.trim()}>
            Convert to Braille →
          </button>
          {letters.length > 0 && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-3)' }}>
              {letters.length} letters · {nav.currentIndex + 1} / {letters.length}
            </span>
          )}
        </div>

        {/* Live text preview with current char highlighted */}
        {letters.length > 0 && (
          <div className="card">
            <div className="text-preview">{buildPreview()}</div>
          </div>
        )}
      </div>

      <div className="page-sidebar">
        {letters.length > 0
          ? <BrailleDisplay {...nav} letters={letters} />
          : (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center', padding: 32, textAlign: 'center' }}>
              <span style={{ fontSize: 32 }}>≡</span>
              <span style={{ color: 'var(--text-3)', fontSize: 13 }}>Paste text and click Convert</span>
            </div>
          )
        }
      </div>
    </div>
  );
}
