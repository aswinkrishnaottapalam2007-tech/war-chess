import React, { useEffect, useRef, useState } from 'react';
import { AppState, View } from 'react-native';
import { usePathname } from 'expo-router';
import { WebView } from 'react-native-webview';
import { AudioModule } from 'expo-audio';
import { api, BASE_URL } from '@/src/api';
import { useApp } from '@/src/context';
import { makeStyles } from '@/src/theme';
import { VoiceContext, idleVoice } from './context';
import type { VoiceTicket } from './transport';

export function VoiceProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState(idleVoice), [ticket, setTicket] = useState<VoiceTicket | null>(null), [blocked, setBlocked] = useState(false);
  const webview = useRef<WebView>(null), attempts = useRef(0), joining = useRef(false), timeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const generation = useRef(0);
  const { user } = useApp(), path = usePathname(), s = useStyles();
  const leave = () => { generation.current += 1; if (timeout.current) clearTimeout(timeout.current); webview.current?.injectJavaScript('window.stopWarVoice?.();true;'); setTicket(null); setState({ ...idleVoice, message: 'Voice disconnected. Text chat is still available.' }); joining.current = false; };
  useEffect(() => { if (!user || (!path.startsWith('/room/') && path !== '/settings' && path !== '/privacy')) leave(); }, [user, path]);
  useEffect(() => { const subscription = AppState.addEventListener('change', value => { if (value === 'background') leave(); }); return () => { subscription.remove(); if (timeout.current) clearTimeout(timeout.current); }; }, []);
  const join = async (code: string) => {
    if (joining.current || state.status === 'connected') return;
    joining.current = true; setState({ ...idleVoice, status: 'connecting', message: 'Preparing your microphone…' });
    const version = ++generation.current;
    try {
      let permission = await AudioModule.getRecordingPermissionsAsync();
      if (!permission.granted && (!permission.canAskAgain || attempts.current >= 2)) { setBlocked(true); throw new Error('Microphone is blocked. Open Settings to allow team voice.'); }
      if (!permission.granted) { attempts.current += 1; permission = await AudioModule.requestRecordingPermissionsAsync(); }
      if (!permission.granted) { setBlocked(!permission.canAskAgain || attempts.current >= 2); throw new Error('Microphone access was declined. Text chat remains available.'); }
      setBlocked(false);
      const freshTicket = await api(`/rooms/${code}/voice`, 'POST');
      if (generation.current !== version || AppState.currentState !== 'active') return;
      setTicket(freshTicket);
      timeout.current = setTimeout(() => { webview.current?.injectJavaScript('window.stopWarVoice?.();true;'); setTicket(null); setState({ ...idleVoice, status: 'error', message: 'Voice did not start on this device. Check microphone permissions and retry.' }); joining.current = false; }, 20000);
    } catch (e: any) { setState({ ...idleVoice, status: 'error', message: e.message }); joining.current = false; }
  };
  return <VoiceContext.Provider value={{ ...state, code: ticket?.code || null, blocked, join, leave, toggleMute: () => webview.current?.injectJavaScript(`window.muteWarVoice?.(${!state.muted});true;`) }}><View style={s.root}>{children}
    {ticket && <WebView key={ticket.ticket} ref={webview} testID="native-voice-host" source={{ uri: `${BASE_URL}/api/voice-client` }} originWhitelist={[BASE_URL]} onShouldStartLoadWithRequest={request => request.url.startsWith(`${BASE_URL}/api/voice-client`)} mediaPlaybackRequiresUserAction={false} allowsInlineMediaPlayback mediaCapturePermissionGrantType="grantIfSameHostElsePrompt" style={s.host} onMessage={event => { try { const data = JSON.parse(event.nativeEvent.data); if (data.type === 'host-ready') webview.current?.injectJavaScript(`window.startWarVoice(${JSON.stringify(ticket)});true;`); else if (data.status) { setState(data); if (data.status !== 'connecting') { joining.current = false; if (timeout.current) clearTimeout(timeout.current); } } } catch {} }} onError={() => { setState({ ...idleVoice, status: 'error', message: 'The secure audio connection could not load. Please retry.' }); setTicket(null); joining.current = false; }} />}
  </View></VoiceContext.Provider>;
}
const useStyles = makeStyles(c => ({ root: { flex: 1, backgroundColor: c.surface }, host: { position: 'absolute', top: 0, left: 0, width: 2, height: 2, opacity: 0.01 } }));