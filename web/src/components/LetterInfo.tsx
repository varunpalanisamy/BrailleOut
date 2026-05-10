import { useEffect, useRef, useState } from 'react';

interface Props {
  char: string;
  activeDots: number[];
  binaryPattern: string;
  index: number;
  total: number;
}

export function LetterInfo({ char, activeDots, binaryPattern, index, total }: Props) {
  const [fading, setFading] = useState(false);
  const prevChar = useRef(char);

  useEffect(() => {
    if (char !== prevChar.current) {
      setFading(true);
      const t = setTimeout(() => {
        setFading(false);
        prevChar.current = char;
      }, 150);
      return () => clearTimeout(t);
    }
  }, [char]);

  return (
    <div className="letter-card">
      <div className={`letter-display${fading ? ' fading' : ''}`}>
        {char.toUpperCase() || '·'}
      </div>

      <div className="letter-meta">
        <div className="letter-meta-row">
          <span className="letter-meta-label">Active dots</span>
          <div className="dot-pills">
            {activeDots.length === 0 ? (
              <span className="dot-pill empty">none</span>
            ) : (
              activeDots.map((d) => (
                <span key={d} className="dot-pill">{d}</span>
              ))
            )}
          </div>
        </div>

        <div className="letter-meta-row">
          <span className="letter-meta-label">Servo pattern</span>
          <div className="binary-pattern">
            {binaryPattern.split('').map((bit, i) => (
              <span key={i} className={`binary-digit ${bit === '1' ? 'one' : 'zero'}`}>
                {bit}
              </span>
            ))}
          </div>
        </div>

        <div className="letter-meta-row">
          <span className="letter-meta-label">
            Position&nbsp;&nbsp;{index + 1} / {total}
          </span>
        </div>
      </div>
    </div>
  );
}
