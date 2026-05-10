interface Props {
  mode: 'mock' | 'live';
  binaryPattern: string;
}

export function StatusBar({ mode, binaryPattern }: Props) {
  return (
    <div className="status-bar">
      <span className="status-mode">
        {mode === 'mock' ? 'MOCK DATA' : 'LIVE PIPELINE'}
      </span>

      <div className="status-sep" />

      <span className="status-pattern-label">servo →</span>

      <span className="status-pattern">
        {binaryPattern.split('').map((bit, i) => (
          <span
            key={i}
            className={`binary-digit ${bit === '1' ? 'one' : 'zero'}`}
          >
            {bit}
          </span>
        ))}
      </span>
    </div>
  );
}
