interface Props {
  onPrev: () => void;
  onNext: () => void;
  canPrev: boolean;
  canNext: boolean;
  letters: string[];
  currentIndex: number;
}

export function NavControls({ onPrev, onNext, canPrev, canNext, letters, currentIndex }: Props) {
  return (
    <div className="nav-card">
      <div className="nav-buttons">
        <button
          className="nav-btn prev"
          onClick={onPrev}
          disabled={!canPrev}
          aria-label="Previous letter"
          title="← Arrow Left"
        >
          ‹
        </button>
        <button
          className="nav-btn next"
          onClick={onNext}
          disabled={!canNext}
          aria-label="Next letter"
          title="→ Arrow Right / Space"
        >
          ›
        </button>
      </div>

      <div className="word-strip">
        {letters.map((letter, i) => (
          <div
            key={i}
            className={`word-tile${i === currentIndex ? ' active' : i < currentIndex ? ' visited' : ''}`}
          >
            {letter === ' ' ? '·' : letter.toUpperCase()}
          </div>
        ))}
      </div>
    </div>
  );
}
