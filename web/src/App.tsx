import { useState } from 'react';
import './styles/global.css';
import { TabBar, type TabId } from './components/TabBar';
import { HomePage }    from './pages/HomePage';
import { CameraPage }  from './pages/CameraPage';
import { KeyboardPage} from './pages/KeyboardPage';
import { TextPage }    from './pages/TextPage';
import { YouTubePage } from './pages/YouTubePage';

export default function App() {
  const [tab, setTab] = useState<TabId>('home');

  return (
    <div className="app-shell">
      <TabBar active={tab} onChange={setTab} />

      {tab === 'home'     && <HomePage    onNavigate={setTab} />}
      {tab === 'camera'   && <CameraPage   />}
      {tab === 'keyboard' && <KeyboardPage />}
      {tab === 'text'     && <TextPage     />}
      {tab === 'youtube'  && <YouTubePage  />}
    </div>
  );
}
