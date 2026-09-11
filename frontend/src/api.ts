import Constants from 'expo-constants';
import { storage } from '@/src/utils/storage';

export const BASE_URL = (Constants.expoConfig?.extra?.backendUrl || process.env.EXPO_PUBLIC_BACKEND_URL || '').replace(/\/$/, '');
export const TOKEN_KEY = 'war-session';
let token = '';
export const getToken = () => token;
export async function setToken(value: string) {
  token = value;
  if (value) await storage.secureSet(TOKEN_KEY, value); else await storage.secureRemove(TOKEN_KEY);
}
export async function restoreToken() {
  token = await storage.secureGet(TOKEN_KEY, '') || '';
  return token;
}
export async function api(path: string, method = 'GET', body?: unknown) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${BASE_URL}/api${path}`, { method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check your details and try again.');
    return data;
  } catch (e: any) {
    if (e.name === 'AbortError') throw new Error('Connection timed out. Please try again.');
    throw e;
  } finally { clearTimeout(timeout); }
}