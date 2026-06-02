import apiClient from './client';
import type { TokenData, UserInfo } from '../lib/types';

export async function login(username: string, password: string): Promise<TokenData> {
  const { data } = await apiClient.post<TokenData>('/auth/login', { username, password });
  return data;
}

export async function register(username: string, password: string): Promise<TokenData> {
  const { data } = await apiClient.post<TokenData>('/auth/register', { username, password });
  return data;
}

export async function getMe(): Promise<UserInfo> {
  const { data } = await apiClient.get<UserInfo>('/auth/me');
  return data;
}
