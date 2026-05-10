import { useCallback, useEffect, useRef, useState } from 'react';
import { BrailleDisplay } from '../components/BrailleDisplay';
import { BRAILLE, dotsToBinary, getActiveDots } from '../data/braille';

export function KeyboardPage() {
  const [typed, setTyped] = useState('');
  const [currentChar, setCurrentChar] = useState('');
  const prevChar = useRef('');

  const activeDots = getActiveDots(currentChar);
  const binaryPattern = dotsToBinary(activeDots);

  const sendChar = useCallback((ch: string) => {
    const dots = getActiveDots(ch);
    const pattern = dotsToBinary(dots);
    fetch('/api/send-pattern', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pattern }),
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      if (e.key === 'Backspace') {
        setTyped((prev) => {
          const next = prev.slice(0, -1);
          const lastCh = next.slice(-1).toLowerCase();
          if (lastCh && lastCh in BRAILLE) {
            setCurrentChar(lastCh);
            prevChar.current = lastCh;
            sendChar(lastCh);
          } else {
            setCurrentChar('');
            prevChar.current = '';
          }
          return next;
        });
        return;
      }

      const ch = e.key === ' ' ? ' ' : e.key.toLowerCase();
      if (ch.length !== 1 || !(ch in BRAILLE)) return;
      e.preventDefault();

      setTyped((prev) => prev + ch);
      setCurrentChar(ch);
      prevChar.current = ch;
      sendChar(ch);
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [sendChar]);

  const clear = () => {
    setTyped('');
    setCurrentChar('');
    prevChar.current = '';
  };

  const letters = currentChar ? [currentChar] : [];

  return (
    <div className="page-two-col">
      <div className="page-main">
        <div className="section-header">
          <div className="section-title">Keyboard → Braille</div>
          <div className="section-sub">
            Press any key (a–z or space) — the Braille cell updates instantly and drives the Arduino.
          </div>
        </div>

        {/* Typed history */}
        <div className="card kb-history">
          {typed ? (
            <div className="kb-typed-text">
              {typed.split('').map((ch, i) => (
                <span
                  key={i}
                  className={`kb-char${i === typed.length - 1 ? ' active' : ''}`}
                >
                  {ch === ' ' ? '·' : ch.toUpperCase()}
                </span>
              ))}
            </div>
          ) : (
            <span className="kb-placeholder">Start typing — press any letter key…</span>
          )}
        </div>

        {/* Big live letter */}
        {currentChar && (
          <div className="live-char-display card">
            {currentChar === ' ' ? '·' : currentChar.toUpperCase()}
          </div>
        )}

        {typed && (
          <button className="action-btn" onClick={clear} style={{ alignSelf: 'flex-start' }}>
            Clear
          </button>
        )}
      </div>

      <div className="page-sidebar">
        <BrailleDisplay
          currentChar={currentChar}
          activeDots={activeDots}
          binaryPattern={binaryPattern}
          currentIndex={0}
          letters={letters}
          next={() => {}}
          prev={() => {}}
          canNext={false}
          canPrev={false}
          isAuto={false}
          speed={1}
          setSpeed={() => {}}
          toggleAuto={() => {}}
        />
      </div>
    </div>
  );
}
