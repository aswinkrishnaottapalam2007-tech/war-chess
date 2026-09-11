import React, { useEffect, useRef, useState } from 'react';
import { usePathname } from 'expo-router';
import { api, BASE_URL } from '@/src/api';
import { useApp } from '@/src/context';
import { VoiceContext, idleVoice } from './context';
import { connectVoice, VoiceConnection } from './transport';

export function VoiceProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState(idleVoice), [code, setCode] = useState<string | null>(null);
  const connection = useRef<VoiceConnection | null>(null), joining = useRef(false), generation = useRef(0);
  const cancellation = useRef<AbortController | null>(null);
  const { user } = useApp(), path = usePathname();
  const leave = () => { generation.current += 1; cancellation.current?.abort(); joining.current = false; connection.current?.close(); connection.current = null; setCode(null); setState({ ...idleVoice, message: 'You left voice. Text chat is still available.' }); };
  useEffect(() => { if (!user || (!path.startsWith('/room/') && path !== '/settings' && path !== '/privacy')) leave(); }, [user, path]);
  useEffect(() => () => { generation.current += 1; cancellation.current?.abort(); connection.current?.close(); }, []);
  const join = async (roomCode: string) => {
    if (joining.current || state.status === 'connected') return;
    joining.current = true; const version = ++generation.current; setCode(roomCode);
    cancellation.current = new AbortController();
    try {
      const result = await connectVoice(BASE_URL, () => api(`/rooms/${roomCode}/voice`, 'POST'), snapshot => { if (generation.current === version) setState(snapshot); }, cancellation.current.signal);
      if (generation.current !== version) result.close(); else connection.current = result;
    } catch { /* The transport emits the actionable error state. */ }
    finally { if (generation.current === version) joining.current = false; }
  };
  return <VoiceContext.Provider value={{ ...state, code, blocked: /blocked|declined/.test(state.message), join, leave, toggleMute: () => connection.current?.mute(!state.muted) }}>{children}</VoiceContext.Provider>;
}