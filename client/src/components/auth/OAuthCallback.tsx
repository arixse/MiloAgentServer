import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { STORAGE_KEYS } from '../../lib/constants';
import { Spinner } from '../ui/Spinner';

export function OAuthCallback() {
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const token = searchParams.get('token');
    const user_id = searchParams.get('user_id');
    const username = searchParams.get('username');
    const error = searchParams.get('error');

    if (error) {
      window.location.replace(`/?error=${encodeURIComponent(error)}`);
      return;
    }

    if (token && user_id && username) {
      // Save token to localStorage, then hard-redirect to /chat so AuthProvider
      // re-initializes with the token and validates it via getMe().
      localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, token);
      window.location.replace('/chat');
    } else {
      window.location.replace('/');
    }
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Spinner size="lg" />
      <span className="ml-3 text-gray-500">正在登录...</span>
    </div>
  );
}
