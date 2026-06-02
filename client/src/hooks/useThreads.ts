import { useContext } from 'react';
import { ThreadContext } from '../contexts/ThreadContext';

export function useThreads() {
  const ctx = useContext(ThreadContext);
  if (!ctx) {
    throw new Error('useThreads must be used within a ThreadProvider');
  }
  return ctx;
}
