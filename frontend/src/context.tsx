import React, { createContext, useContext, useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { api, restoreToken, setToken } from './api';
import { restoreTheme, makeStyles, useTheme } from './theme';
import { storage } from './utils/storage';
import { User } from './types';

type Context = { user: User | null; loading: boolean; signIn: (data: { user: User; token: string }) => Promise<void>; signOut: () => Promise<void>; notify: (text: string) => void; volume: number; setVolume: (v: number) => void };
const AppContext = createContext<Context>(null as any);
export const useApp = () => useContext(AppContext);
export function AppProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null), [loading, setLoading] = useState(true), [toast, setToast] = useState(''), [volume, setVolumeState] = useState(0.65);
  const insets = useSafeAreaInsets(), s = useStyles(), { colors } = useTheme();
  useEffect(() => { (async () => { await restoreTheme(); setVolumeState(Number(await storage.getItem('war-volume', 0.65))); if (await restoreToken()) { try { setUser(await api('/auth/me')); } catch { await setToken(''); } } setLoading(false); })(); }, []);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(''), 5000); return () => clearTimeout(t); }, [toast]);
  const signIn = async (data: { user: User; token: string }) => { await setToken(data.token); setUser(data.user); };
  const signOut = async () => { try { await api('/auth/logout', 'POST'); } finally { await setToken(''); setUser(null); } };
  const setVolume = (v: number) => { setVolumeState(v); storage.setItem('war-volume', v); };
  return <AppContext.Provider value={{ user, loading, signIn, signOut, notify: setToast, volume, setVolume }}>
    {children}
    {!!toast && <View style={[s.toast, { top: insets.top + 12 }]} testID="notification-toast"><Ionicons name="information-circle-outline" size={22} color={colors.brand} /><Text style={s.text}>{toast}</Text><Pressable testID="dismiss-toast-button" accessibilityLabel="Dismiss notification" onPress={() => setToast('')} style={s.close}><Ionicons name="close" size={20} color={colors.onSurface} /></Pressable></View>}
  </AppContext.Provider>;
}
const useStyles = makeStyles(c => ({ toast: { position: 'absolute', left: 16, right: 16, maxWidth: 700, alignSelf: 'center', backgroundColor: c.surfaceTertiary, borderColor: c.borderStrong, borderWidth: 1, borderRadius: 12, padding: 14, flexDirection: 'row', gap: 10, alignItems: 'center', elevation: 12 }, text: { fontFamily: 'Manrope', fontSize: 14, lineHeight: 21, color: c.onSurface, flex: 1 }, close: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' } }));