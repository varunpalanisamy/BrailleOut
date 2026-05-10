import { DOT_POSITION } from '../data/braille';

interface Props {
  activeDots: number[];
  size?: 'sm' | 'md';
}

const SIZES = {
  sm: { w: 28, h: 42, r: 5,   cols: [7, 21],   rows: [7, 21, 35]   },
  md: { w: 40, h: 60, r: 7.5, cols: [10.5, 29.5], rows: [10.5, 30, 49.5] },
};

export function MiniCell({ activeDots, size = 'md' }: Props) {
  const { w, h, r, cols, rows } = SIZES[size];

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width={w}
      height={h}
      xmlns="http://www.w3.org/2000/svg"
    >
      {[1, 2, 3, 4, 5, 6].map((dot) => {
        const [row, col] = DOT_POSITION[dot];
        const cx = cols[col];
        const cy = rows[row];
        const active = activeDots.includes(dot);
        return (
          <circle
            key={dot}
            cx={cx}
            cy={cy}
            r={r}
            fill={active ? 'rgba(139,92,246,0.9)' : 'rgba(255,255,255,0.04)'}
            stroke={active ? 'none' : 'rgba(255,255,255,0.22)'}
            strokeWidth={active ? 0 : 1}
            filter={active ? 'url(#mini-glow)' : 'none'}
          />
        );
      })}
      <defs>
        <filter id="mini-glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
    </svg>
  );
}
