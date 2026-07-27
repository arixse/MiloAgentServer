import { createContext, useCallback, useEffect, useReducer, type ReactNode } from 'react';
import { STORAGE_KEYS } from '../lib/constants';
import type { UserInfo } from '../lib/types';
import { getMe } from '../api/auth';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
interface AuthState {
  user: UserInfo | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
}

const initialState: AuthState = {
  user: null,
  token: localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN),
  isLoading: true,
  isAuthenticated: false,
  error: null,
};

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
type AuthAction =
  | { type: 'AUTH_SUCCESS'; payload: { user: UserInfo; token: string } }
  | { type: 'AUTH_FAILURE'; payload: string }
  | { type: 'LOGOUT' }
  | { type: 'INIT_COMPLETE'; payload: { user: UserInfo | null } };

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'AUTH_SUCCESS': {
      const { user, token } = action.payload;
      localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, token);
      return { ...state, isLoading: false, isAuthenticated: true, user, token, error: null };
    }
    case 'AUTH_FAILURE':
      localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
      return { ...state, isLoading: false, isAuthenticated: false, user: null, token: null, error: action.payload };
    case 'LOGOUT':
      localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
      return { ...state, isLoading: false, isAuthenticated: false, user: null, token: null, error: null };
    case 'INIT_COMPLETE':
      return { ...state, isLoading: false, isAuthenticated: !!action.payload.user, user: action.payload.user };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
interface AuthContextValue {
  user: UserInfo | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
  logout: () => void;
  clearError: () => void;
  handleOAuthCallback: (token: string, user: UserInfo) => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  // Initialize: check if existing token is valid
  useEffect(() => {
    const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
    if (!token) {
      dispatch({ type: 'INIT_COMPLETE', payload: { user: null } });
      return;
    }
    getMe()
      .then((user) => dispatch({ type: 'INIT_COMPLETE', payload: { user } }))
      .catch(() => {
        localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
        dispatch({ type: 'INIT_COMPLETE', payload: { user: null } });
      });
  }, []);

  const logout = useCallback(() => {
    dispatch({ type: 'LOGOUT' });
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: 'AUTH_FAILURE', payload: '' });
  }, []);

  const handleOAuthCallback = useCallback((token: string, user: UserInfo) => {
    dispatch({ type: 'AUTH_SUCCESS', payload: { user, token } });
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user: state.user,
        isLoading: state.isLoading,
        isAuthenticated: state.isAuthenticated,
        error: state.error,
        logout,
        clearError,
        handleOAuthCallback,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
