import { DOT_POSITION } from '../data/braille';

interface Props {
  activeDots: number[];
}

const CELL_W = 120;
const CELL_H = 180;
const PAD = 24;
const R = 22;
const COL_X = [PAD + R, CELL_W - PAD - R];
const ROW_Y = [PAD + R, CELL_H / 2, CELL_H - PAD - R];

function dotCoords(dot: number): [number, number] {
  const [row, col] = DOT_POSITION[dot];
  return [COL_X[col], ROW_Y[row]];
}

export function BrailleCell({ activeDots }: Props) {
  return (
    <svg
      className="braille-cell-svg"
      viewBox={`0 0 ${CELL_W} ${CELL_H}`}
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Braille cell"
    >
      <defs>
        <filter id="dot-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="5" result="blur" />
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
          <g key={dot}>
            <circle
              className="braille-dot"
              cx={cx}
              cy={cy}
              r={R}
              fill={active ? 'var(--dot-active)' : 'var(--dot-inactive-fill)'}
              stroke={active ? 'none' : 'var(--dot-inactive-stroke)'}
              strokeWidth={active ? 0 : 1.5}
              filter={active ? 'url(#dot-glow)' : 'none'}
              opacity={active ? 1 : 0.7}
            />
            <text
              className={`braille-dot-number${active ? ' active' : ''}`}
              x={cx}
              y={cy + R + 10}
              textAnchor="middle"
              fontSize="9"
            >
              {dot}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
