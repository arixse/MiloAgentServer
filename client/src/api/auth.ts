import apiClient from './client';
import type { UserInfo } from '../lib/types';

export async function getMe(): Promise<UserInfo> {
  const { data } = await apiClient.get<UserInfo>('/auth/me');
  return data;
}
