import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { DOT_POSITION, dotsToBinary, getActiveDots } from '../data/braille';

const DEMO_WORD = 'braille'.split('');

// Geometry for the large hero Braille cell
const DW = 200, DH = 300, DR = 33;
const DCOLS = [55, 145];
const DROWS = [55, 150, 245];

const TEST_STEPS: { label: string; dots: number[] }[] = [
  { label: 'All servos', dots: [1, 2, 3, 4, 5, 6] },
  { label: 'Dot 1', dots: [1] },
  { label: 'Dot 2', dots: [2] },
  { label: 'Dot 3', dots: [3] },
  { label: 'Dot 4', dots: [4] },
  { label: 'Dot 5', dots: [5] },
  { label: 'Dot 6', dots: [6] },
];

const TW = 80, TH = 120, TR = 12;
const TCOLS = [22, 58];
const TROWS = [18, 60, 102];

async function sendPattern(pattern: string) {
  await fetch('/api/send-pattern', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pattern }),
  }).catch(() => {});
}

export function HomePage() {
  const [demoIdx, setDemoIdx] = useState(0);
  const [testing, setTesting] = useState(false);
  const [testStepIdx, setTestStepIdx] = useState(-1);

  useEffect(() => {
    const t = setInterval(() => {
      setDemoIdx((i) => (i + 1) % DEMO_WORD.length);
    }, 900);
    return () => clearInterval(t);
  }, []);

  async function runTest() {
    setTesting(true);
    const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

    for (let i = 0; i < TEST_STEPS.length; i++) {
      setTestStepIdx(i);
      const pattern = dotsToBinary(TEST_STEPS[i].dots);
      await sendPattern(pattern);
      // 300 ms: Arduino holds dots up (backend auto-resets at 300ms)
      // extra 700 ms: pause so the user can see the servo move down before next step
      await delay(i === 0 ? 1200 : 900);
    }

    setTestStepIdx(-1);
    setTesting(false);
  }

  const demoChar = DEMO_WORD[demoIdx];
  const demoDots = getActiveDots(demoChar);
  const activeStep = testStepIdx >= 0 ? TEST_STEPS[testStepIdx] : null;

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

        {/* ── Servo test ── */}
        <motion.div
          className="servo-test-section"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <button
            className={`servo-test-btn${testing ? ' running' : ''}`}
            onClick={runTest}
            disabled={testing}
          >
            {testing ? 'Testing…' : 'Run Servo Test'}
          </button>

          {activeStep && (
            <div className="servo-test-status">
              <svg viewBox={`0 0 ${TW} ${TH}`} width={TW} height={TH}>
                {[1, 2, 3, 4, 5, 6].map((dot) => {
                  const [row, col] = DOT_POSITION[dot];
                  const cx = TCOLS[col];
                  const cy = TROWS[row];
                  const active = activeStep.dots.includes(dot);
                  return (
                    <circle
                      key={dot}
                      cx={cx} cy={cy} r={TR}
                      fill={active ? '#7c3aed' : 'var(--dot-inactive-fill)'}
                      stroke={active ? 'none' : 'var(--dot-inactive-stroke)'}
                      strokeWidth={1.5}
                      style={{ transition: 'fill 0.15s' }}
                    />
                  );
                })}
              </svg>
              <div className="servo-test-label">
                <span className="servo-test-step">{activeStep.label}</span>
                <span className="servo-test-progress">{testStepIdx + 1} / {TEST_STEPS.length}</span>
              </div>
            </div>
          )}
        </motion.div>


      </div>
    </div>
  );
}
