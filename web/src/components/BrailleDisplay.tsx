import { useEffect, useRef, useState } from 'react';
import { DOT_POSITION } from '../data/braille';

interface Props {
  currentChar: string;
  activeDots: number[];
  binaryPattern: string;
  currentIndex: number;
  letters: string[];
  next: () => void;
  prev: () => void;
  canNext: boolean;
  canPrev: boolean;
  isAuto: boolean;
  speed: number;
  setSpeed: (s: number) => void;
  toggleAuto: () => void;
}

// SVG geometry — matches .bd-svg 180×270
const W = 180, H = 270, R = 33;
const COLS = [48, 132];
const ROWS = [48, 135, 222];

function dotCoords(dot: number): [number, number] {
  const [row, col] = DOT_POSITION[dot];
  return [COLS[col], ROWS[row]];
}

export function BrailleDisplay({
  currentChar, activeDots, binaryPattern,
  currentIndex, letters,
  next, prev, canNext, canPrev,
  isAuto, speed, setSpeed, toggleAuto,
}: Props) {
  const total = letters.length;
  const [fading, setFading] = useState(false);
  const prevChar = useRef(currentChar);

  useEffect(() => {
    if (currentChar !== prevChar.current) {
      setFading(true);
      const t = setTimeout(() => {
        setFading(false);
        prevChar.current = currentChar;
      }, 140);
      return () => clearTimeout(t);
    }
  }, [currentChar]);

  const displayChar = currentChar === ' ' ? '·' : currentChar.toUpperCase();

  return (
    <div className="braille-display">
      <span className="bd-label">Braille Cell</span>

      {/* SVG dot grid */}
      <svg className="bd-svg" viewBox={`0 0 ${W} ${H}`} xmlns="http://www.w3.org/2000/svg" style={{ width: 180, height: 270 }}>
        <defs>
          <filter id="dot-glow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {[1, 2, 3, 4, 5, 6].map((dot) => {
          const [cx, cy] = dotCoords(dot);
          const active = activeDots.includes(dot);
          return (
            <circle
              key={dot}
              className="bd-dot"
              cx={cx} cy={cy} r={R}
              fill={active ? 'var(--dot-active-fill)' : 'var(--dot-inactive-fill)'}
              stroke={active ? 'none' : 'var(--dot-inactive-stroke)'}
              strokeWidth={active ? 0 : 1.5}
              filter={active ? 'url(#dot-glow)' : 'none'}
              opacity={active ? 1 : 0.75}
            />
          );
        })}
      </svg>

      {/* Current letter */}
      <div className={`bd-char${fading ? ' fading' : ''}`}>{displayChar}</div>

      {/* Dot info */}
      <div className="bd-info">
        <div className="bd-info-row">
          <span className="bd-info-label">Active dots</span>
          <div className="dot-pills">
            {activeDots.length === 0
              ? <span className="dot-pill none">none</span>
              : activeDots.map((d) => <span key={d} className="dot-pill">{d}</span>)
            }
          </div>
        </div>

        <div className="bd-info-row">
          <span className="bd-info-label">Servo pattern</span>
          <div className="binary-row">
            {binaryPattern.split('').map((bit, i) => (
              <span key={i} className={bit === '1' ? 'bit-on' : 'bit-off'}>{bit}</span>
            ))}
          </div>
        </div>
      </div>

      <span className="bd-progress">{currentIndex + 1} / {total}</span>

      {/* Navigation */}
      <div className="nav-row">
        <button className="nav-btn" onClick={prev} disabled={!canPrev || isAuto} aria-label="Previous">‹</button>
        <button className="nav-btn next" onClick={next} disabled={!canNext || isAuto} aria-label="Next">›</button>
      </div>

      {/* Auto mode controls — only shown when there are multiple letters to step through */}
      {letters.length > 1 && (
        <div className="auto-controls">
          <button
            className={`auto-btn${isAuto ? ' active' : ''}`}
            onClick={toggleAuto}
            disabled={letters.length === 0}
          >
            {isAuto ? '⏹ Stop' : '▶ Auto'}
          </button>
          <div className="speed-row">
            <span className="speed-label">0.3s</span>
            <input
              type="range"
              className="speed-slider"
              min={0.3}
              max={3}
              step={0.05}
              value={speed}
              onChange={(e) => setSpeed(parseFloat(e.target.value))}
            />
            <span className="speed-label">3s</span>
            <span className="speed-value">{speed.toFixed(1)}s</span>
          </div>
        </div>
      )}

      {/* Word strip */}
      <div className="word-strip">
        {letters.map((ch, i) => (
          <div
            key={i}
            className={`word-tile${i === currentIndex ? ' active' : i < currentIndex ? ' visited' : ''}`}
          >
            {ch === ' ' ? '·' : ch.toUpperCase()}
          </div>
        ))}
      </div>
    </div>
  );
}
