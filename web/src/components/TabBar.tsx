export type TabId = 'home' | 'camera' | 'keyboard' | 'text' | 'youtube';

const TABS: { id: TabId; icon: string; label: string }[] = [
  { id: 'home',     icon: '⬡',  label: 'Home'     },
  { id: 'camera',   icon: '◎',  label: 'Camera'   },
  { id: 'keyboard', icon: '⌨',  label: 'Keyboard' },
  { id: 'text',     icon: '≡',  label: 'Text'     },
  { id: 'youtube',  icon: '▷',  label: 'YouTube'  },
];

// braille pattern for 'b' used as logo
const LOGO_DOTS = [1, 2];
const LOGO_ORDER = [1, 4, 2, 5, 3, 6];

interface Props {
  active: TabId;
  onChange: (id: TabId) => void;
}

export function TabBar({ active, onChange }: Props) {
  return (
    <nav className="tab-bar">
      <div className="tab-bar-logo">
        <div className="tab-logo-dots">
          {LOGO_ORDER.map((dot) => (
            <div
              key={dot}
              className={`tab-logo-dot${LOGO_DOTS.includes(dot) ? ' on' : ''}`}
            />
          ))}
        </div>
        <span className="tab-bar-name">Braille</span>
      </div>

      {TABS.map(({ id, icon, label }) => (
        <button
          key={id}
          className={`tab-btn${active === id ? ' active' : ''}`}
          onClick={() => onChange(id)}
        >
          <span className="tab-icon">{icon}</span>
          {label}
        </button>
      ))}
    </nav>
  );
}
