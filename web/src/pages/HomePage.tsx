import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MiniCell } from '../components/MiniCell';
import { DOT_POSITION, getActiveDots } from '../data/braille';

const DEMO_WORD = 'braille'.split('');
const VARUN   = 'varun'.split('');
const SHIVANI = 'shivani'.split('');

// Geometry for the large hero Braille cell
const DW = 200, DH = 300, DR = 33;
const DCOLS = [55, 145];
const DROWS = [55, 150, 245];

function BrailleNameWord({ word }: { word: string[] }) {
  return (
    <>
      {word.map((ch, i) => (
        <motion.div
          key={i}
          className="hero-letter-cell"
          initial={{ opacity: 0, y: 12, scale: 0.7 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ delay: 0.6 + i * 0.06, type: 'spring', stiffness: 300, damping: 22 }}
        >
          <MiniCell activeDots={getActiveDots(ch)} size="sm" />
        </motion.div>
      ))}
    </>
  );
}

export function HomePage() {
  const [demoIdx, setDemoIdx] = useState(0);

  useEffect(() => {
    const t = setInterval(() => {
      setDemoIdx((i) => (i + 1) % DEMO_WORD.length);
    }, 900);
    return () => clearInterval(t);
  }, []);

  const demoChar = DEMO_WORD[demoIdx];
  const demoDots = getActiveDots(demoChar);

  return (
    <div className="home-page">
      <div className="home-bg-pattern" />

      <div className="home-content">

        {/* ── Title ── */}
        <motion.div
          className="hero-title"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
        >
          <h1><span>BrailleOut</span></h1>
        </motion.div>

        {/* ── Live cycling Braille cell ── */}
        <motion.div
          className="home-demo"
          initial={{ opacity: 0, scale: 0.88 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.15, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="home-demo-inner">
            {/* Braille cell SVG */}
            <div className="home-demo-cell">
              <svg viewBox={`0 0 ${DW} ${DH}`} width={DW} height={DH}>
                <defs>
                  <filter id="hglow" x="-80%" y="-80%" width="260%" height="260%">
                    <feGaussianBlur stdDeviation="7" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>
                {[1, 2, 3, 4, 5, 6].map((dot) => {
                  const [row, col] = DOT_POSITION[dot];
                  const cx = DCOLS[col];
                  const cy = DROWS[row];
                  const active = demoDots.includes(dot);
                  return (
                    <circle
                      key={dot}
                      className="home-demo-dot"
                      cx={cx} cy={cy} r={DR}
                      fill={active ? '#7c3aed' : 'var(--dot-inactive-fill)'}
                      stroke={active ? 'none' : 'var(--dot-inactive-stroke)'}
                      strokeWidth={active ? 0 : 1.5}
                      filter={active ? 'url(#hglow)' : 'none'}
                      opacity={active ? 1 : 0.55}
                    />
                  );
                })}
              </svg>
            </div>

            {/* Large letter */}
            <div className="home-demo-right">
              <AnimatePresence mode="wait">
                <motion.span
                  key={demoChar}
                  className="home-demo-letter"
                  initial={{ opacity: 0, y: -18, filter: 'blur(6px)' }}
                  animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                  exit={{ opacity: 0, y: 18, filter: 'blur(6px)' }}
                  transition={{ duration: 0.22, ease: 'easeInOut' }}
                >
                  {demoChar.toUpperCase()}
                </motion.span>
              </AnimatePresence>
              <span className="home-demo-caption">
                live · cycling<br />"BRAILLE"
              </span>
            </div>
          </div>
        </motion.div>

        {/* ── Names in Braille ── */}
        <div className="names-row">
          <div className="names-braille">
            <div className="name-group">
              <div className="name-cells">
                <BrailleNameWord word={VARUN} />
              </div>
              <span className="name-label">Varun</span>
            </div>

            <motion.span
              className="names-divider"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.9 }}
            >
              &amp;
            </motion.span>

            <div className="name-group">
              <div className="name-cells">
                <BrailleNameWord word={SHIVANI} />
              </div>
              <span className="name-label">Shivani</span>
            </div>
          </div>

          <motion.span
            className="hackdavis-badge"
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 1.1, type: 'spring', stiffness: 260, damping: 20 }}
          >
            HackDavis 2026
          </motion.span>
        </div>

      </div>
    </div>
  );
}
