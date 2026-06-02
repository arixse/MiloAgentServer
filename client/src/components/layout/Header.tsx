import { useAuth } from '../../hooks/useAuth';
import { Avatar } from '../ui/Avatar';
import { Button } from '../ui/Button';
import { LogOut } from 'lucide-react';

export function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="h-14 border-b border-gray-200 flex items-center justify-between px-4 bg-white shrink-0">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-black text-white flex items-center justify-center">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <span className="font-semibold text-sm text-gray-900">Milo Agent</span>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Avatar name={user?.username || 'U'} size="sm" />
          <span className="text-sm text-gray-600 hidden sm:block">{user?.username}</span>
        </div>
        <Button variant="ghost" size="sm" onClick={logout}>
          <LogOut className="w-4 h-4" />
        </Button>
      </div>
    </header>
  );
}
