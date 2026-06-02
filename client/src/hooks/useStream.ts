import { useContext } from 'react';
import { StreamContext } from '../contexts/StreamContext';

export function useStream() {
  const ctx = useContext(StreamContext);
  if (!ctx) {
    throw new Error('useStream must be used within a StreamProvider');
  }
  return ctx;
}
