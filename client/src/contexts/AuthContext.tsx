import { createContext, useCallback, useEffect, useReducer, type ReactNode } from 'react';
import { STORAGE_KEYS } from '../lib/constants';
import type { UserInfo } from '../lib/types';
import * as authApi from '../api/auth';

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
  | { type: 'AUTH_START' }
  | { type: 'AUTH_SUCCESS'; payload: { user: UserInfo; token: string } }
  | { type: 'AUTH_FAILURE'; payload: string }
  | { type: 'LOGOUT' }
  | { type: 'INIT_COMPLETE'; payload: { user: UserInfo | null } };

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'AUTH_START':
      return { ...state, isLoading: true, error: null };
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
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  clearError: () => void;
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
    authApi
      .getMe()
      .then((user) => dispatch({ type: 'INIT_COMPLETE', payload: { user } }))
      .catch(() => {
        localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
        dispatch({ type: 'INIT_COMPLETE', payload: { user: null } });
      });
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    dispatch({ type: 'AUTH_START' });
    try {
      const data = await authApi.login(username, password);
      dispatch({ type: 'AUTH_SUCCESS', payload: { user: { user_id: data.user_id, username: data.username }, token: data.access_token } });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '登录失败';
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || message;
      dispatch({ type: 'AUTH_FAILURE', payload: detail });
      throw err;
    }
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    dispatch({ type: 'AUTH_START' });
    try {
      const data = await authApi.register(username, password);
      dispatch({ type: 'AUTH_SUCCESS', payload: { user: { user_id: data.user_id, username: data.username }, token: data.access_token } });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '注册失败';
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || message;
      dispatch({ type: 'AUTH_FAILURE', payload: detail });
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    dispatch({ type: 'LOGOUT' });
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: 'AUTH_FAILURE', payload: '' });
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user: state.user,
        isLoading: state.isLoading,
        isAuthenticated: state.isAuthenticated,
        error: state.error,
        login,
        register,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
