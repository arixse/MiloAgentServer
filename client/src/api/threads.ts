import apiClient from './client';
import type { ThreadInfo } from '../lib/types';

export async function createThread(metadata?: Record<string, unknown>): Promise<ThreadInfo> {
  const { data } = await apiClient.post<ThreadInfo>('/threads', { metadata });
  return data;
}

export async function listThreads(): Promise<ThreadInfo[]> {
  const { data } = await apiClient.get<ThreadInfo[]>('/threads');
  return data;
}

export async function getThread(threadId: string): Promise<ThreadInfo> {
  const { data } = await apiClient.get<ThreadInfo>(`/threads/${threadId}`);
  return data;
}

export async function deleteThread(threadId: string): Promise<void> {
  await apiClient.delete(`/threads/${threadId}`);
}

export async function getThreadState(threadId: string): Promise<{ thread_id: string; user_id: string; values: Record<string, unknown> }> {
  const { data } = await apiClient.get(`/threads/${threadId}/state`);
  return data;
}
