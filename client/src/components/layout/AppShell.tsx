import { Outlet } from 'react-router-dom';
import { ThreadProvider } from '../../contexts/ThreadContext';
import { StreamProvider } from '../../contexts/StreamContext';
import { Header } from './Header';
import { ThreadHistory } from '../thread/ThreadHistory';

export function AppShell() {
  return (
    <ThreadProvider>
      <StreamProvider>
        <div className="h-screen flex flex-col bg-white">
          <Header />
          <div className="flex-1 flex overflow-hidden">
            <ThreadHistory />
            <main className="flex-1 flex flex-col min-w-0">
              <Outlet />
            </main>
          </div>
        </div>
      </StreamProvider>
    </ThreadProvider>
  );
}
