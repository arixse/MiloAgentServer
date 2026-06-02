import { createContext, useCallback, useEffect, useReducer, type ReactNode } from 'react';
import type { ThreadInfo } from '../lib/types';
import * as threadsApi from '../api/threads';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
interface ThreadState {
  threads: ThreadInfo[];
  activeThreadId: string | null;
  isLoading: boolean;
}

const initialState: ThreadState = {
  threads: [],
  activeThreadId: null,
  isLoading: false,
};

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
type ThreadAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_THREADS'; payload: ThreadInfo[] }
  | { type: 'ADD_THREAD'; payload: ThreadInfo }
  | { type: 'REMOVE_THREAD'; payload: string }
  | { type: 'SELECT_THREAD'; payload: string | null };

function threadReducer(state: ThreadState, action: ThreadAction): ThreadState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_THREADS':
      return { ...state, threads: action.payload, isLoading: false };
    case 'ADD_THREAD':
      return { ...state, threads: [action.payload, ...state.threads], activeThreadId: action.payload.thread_id };
    case 'REMOVE_THREAD': {
      const filtered = state.threads.filter((t) => t.thread_id !== action.payload);
      const active = state.activeThreadId === action.payload ? null : state.activeThreadId;
      if (filtered.length > 0 && !active) {
        return { ...state, threads: filtered, activeThreadId: filtered[0].thread_id };
      }
      return { ...state, threads: filtered, activeThreadId: active };
    }
    case 'SELECT_THREAD':
      return { ...state, activeThreadId: action.payload };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
interface ThreadContextValue {
  threads: ThreadInfo[];
  activeThreadId: string | null;
  isLoading: boolean;
  fetchThreads: () => Promise<void>;
  createThread: () => Promise<ThreadInfo>;
  selectThread: (id: string) => void;
  deleteThread: (id: string) => Promise<void>;
}

export const ThreadContext = createContext<ThreadContextValue | null>(null);

export function ThreadProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(threadReducer, initialState);

  const fetchThreads = useCallback(async () => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const threads = await threadsApi.listThreads();
      dispatch({ type: 'SET_THREADS', payload: threads });
      if (threads.length > 0 && !state.activeThreadId) {
        dispatch({ type: 'SELECT_THREAD', payload: threads[0].thread_id });
      }
    } catch {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.activeThreadId]);

  const createThread = useCallback(async () => {
    const thread = await threadsApi.createThread();
    dispatch({ type: 'ADD_THREAD', payload: thread });
    return thread;
  }, []);

  const selectThread = useCallback((id: string) => {
    dispatch({ type: 'SELECT_THREAD', payload: id });
  }, []);

  const deleteThread = useCallback(async (id: string) => {
    await threadsApi.deleteThread(id);
    dispatch({ type: 'REMOVE_THREAD', payload: id });
  }, []);

  // Auto-fetch threads on mount
  useEffect(() => {
    fetchThreads();
  }, [fetchThreads]);

  return (
    <ThreadContext.Provider
      value={{
        threads: state.threads,
        activeThreadId: state.activeThreadId,
        isLoading: state.isLoading,
        fetchThreads,
        createThread,
        selectThread,
        deleteThread,
      }}
    >
      {children}
    </ThreadContext.Provider>
  );
}
