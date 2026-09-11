import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { api, BASE_URL, getToken } from '@/src/api';
import { Room } from '@/src/types';
import { useApp } from '@/src/context';

export function useRoom(code: string) {
  const [room, setRoom] = useState<Room | null>(null), [error, setError] = useState(''), [connected, setConnected] = useState(false), [busy, setBusy] = useState(false);
  const offset = useRef(0), { notify } = useApp();
  const update = useCallback((data: Room) => { offset.current = data.server_time * 1000 - Date.now(); setRoom(prev => !prev || data.revision >= prev.revision ? data : prev); setError(''); }, []);
  const refresh = useCallback(async () => { try { update(await api(`/rooms/${code}`)); } catch (e: any) { setError(e.message); } }, [code, update]);
  useEffect(() => {
    let closed = false, ws: WebSocket | null = null, reconnect: ReturnType<typeof setTimeout>;
    const connect = () => {
      if (closed) return;
      ws = new WebSocket(`${BASE_URL.replace(/^http/, 'ws')}/api/ws/${code}`);
      ws.onopen = () => { ws?.send(JSON.stringify({ token: getToken() })); };
      ws.onmessage = event => { try { const data = JSON.parse(event.data); if (data.type === 'state') { update(data.room); setConnected(true); } } catch {} };
      ws.onclose = () => { setConnected(false); if (!closed) reconnect = setTimeout(connect, 2500); };
      ws.onerror = () => { setConnected(false); };
    };
    refresh(); connect();
    const poll = setInterval(refresh, 5000);
    const ping = setInterval(() => { if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' })); }, 10000);
    const listener = AppState.addEventListener('change', state => { if (state === 'active') refresh(); });
    return () => { closed = true; clearTimeout(reconnect); clearInterval(poll); clearInterval(ping); listener.remove(); ws?.close(); };
  }, [code, refresh, update]);
  const act = async (data: Record<string, unknown>) => { setBusy(true); try { update(await api(`/rooms/${code}/actions`, 'POST', data)); return true; } catch (e: any) { notify(e.message); refresh(); return false; } finally { setBusy(false); } };
  return { room, error, connected, busy, act, refresh, offset };
}