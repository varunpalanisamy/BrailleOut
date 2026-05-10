import { MiniCell } from '../components/MiniCell';
import { getActiveDots } from '../data/braille';
import type { TabId } from '../components/TabBar';

const HACKDAVIS = 'hackdavis'.split('');
const VARUN     = 'varun'.split('');
const SHIVANI   = 'shivani'.split('');

const FEATURES: { icon: string; name: string; desc: string; tab: TabId }[] = [
  { icon: '◎', name: 'Camera → Braille', desc: 'Point the camera at text and convert it to Braille in real time.', tab: 'camera'   },
  { icon: '⌨', name: 'Keyboard → Braille', desc: 'Type anything and watch the Braille cell update instantly.', tab: 'keyboard' },
  { icon: '≡', name: 'Text → Braille',    desc: 'Paste an article or any text and navigate it letter by letter.', tab: 'text'     },
  { icon: '▷', name: 'YouTube → Braille', desc: 'Drop a YouTube link and read the transcript in Braille.', tab: 'youtube'  },
];

interface Props {
  onNavigate: (tab: TabId) => void;
}

function BrailleWord({ word, size = 'md' }: { word: string[]; size?: 'sm' | 'md' }) {
  return (
    <>
      {word.map((ch, i) => (
        <div key={i} className="hero-letter-cell">
          <MiniCell activeDots={getActiveDots(ch)} size={size} />
          <span className="hero-letter-label">{ch.toUpperCase()}</span>
        </div>
      ))}
    </>
  );
}

export function HomePage({ onNavigate }: Props) {
  return (
    <div className="home-page">
      <div className="home-bg-pattern" />

      <div className="home-content">
        {/* HACKDAVIS in braille */}
        <div className="hero-braille-word">
          <BrailleWord word={HACKDAVIS} size="md" />
        </div>

        {/* Title */}
        <div className="hero-title">
          <h1>AI-Powered <span>Braille Display</span></h1>
          <p>
            A real-time pipeline that converts text, camera input, and video into
            Grade&nbsp;1 Braille — displayed visually and physically via servo motors.
          </p>
        </div>

        {/* Feature cards */}
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <div key={f.tab} className="feature-card" onClick={() => onNavigate(f.tab)}>
              <div className="feature-icon">{f.icon}</div>
              <div className="feature-name">{f.name}</div>
              <div className="feature-desc">{f.desc}</div>
              <div className="feature-arrow">Try it →</div>
            </div>
          ))}
        </div>

        {/* Names in braille */}
        <div className="names-row">
          <div className="names-braille">
            <div className="name-group">
              <div className="name-cells">
                <BrailleWord word={VARUN} size="sm" />
              </div>
              <span className="name-label">Varun</span>
            </div>

            <span className="names-divider">&amp;</span>

            <div className="name-group">
              <div className="name-cells">
                <BrailleWord word={SHIVANI} size="sm" />
              </div>
              <span className="name-label">Shivani</span>
            </div>
          </div>
          <span className="hackdavis-badge">HackDavis 2026</span>
        </div>
      </div>
    </div>
  );
}
