import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { Screen, Button, Notice, Sheet } from '@/src/components/ui';
import { Lobby } from '@/src/components/Lobby';
import { Match } from '@/src/components/Match';
import { Chat } from '@/src/components/Chat';
import { useRoom } from '@/src/useRoom';
import { useApp } from '@/src/context';
import { makeStyles, useTheme } from '@/src/theme';
import { VoiceStatusBar } from '@/src/components/VoicePanel';

export default function RoomScreen() {
  const { code } = useLocalSearchParams<{ code: string }>(), { user, loading } = useApp(), { room, error, connected, busy, act, refresh, offset } = useRoom(code), [chat, setChat] = useState(false);
  const s = useStyles(), { colors: c } = useTheme();
  useEffect(() => { if (!loading && !user) router.replace('/auth'); }, [loading, user]);
  return <Screen title={room?.status === 'lobby' ? 'The war room' : 'The battlefield'} eyebrow={room?.status === 'lobby' ? 'ASSEMBLE YOUR ALLIANCE' : `WAR CHESS / ${code}`} scroll={false} right={<View style={s.connection}><View style={[s.dot, { backgroundColor: connected ? c.success : c.warning }]} /><Text testID="connection-status" style={s.status}>{connected ? 'LIVE' : 'SYNCING'}</Text></View>}>
    <VoiceStatusBar code={code} />{!room ? <View style={s.loading}>{error ? <><Notice text={error} /><Button testID="retry-room-button" title="RECONNECT" onPress={refresh} /><Button testID="return-rooms-button" title="BACK TO WAR ROOMS" variant="secondary" onPress={() => router.replace('/join')} /></> : <ActivityIndicator size="large" color={c.brand} />}</View> : <>{error && <Notice text={error} testID="room-sync-error" />}{room.status === 'lobby' ? <Lobby room={room} act={act} busy={busy} onChat={() => setChat(true)} /> : <Match room={room} act={act} busy={busy} offset={offset} />}<Sheet visible={chat && room.status === 'lobby'} title="Team communications" onClose={() => setChat(false)}><Chat room={room} act={act} /></Sheet></>}
  </Screen>;
}
const useStyles = makeStyles(c => ({ loading: { flex: 1, justifyContent: 'center', padding: 24, gap: 20 }, connection: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingRight: 7 }, dot: { width: 5, height: 5, borderRadius: 3 }, status: { fontFamily: 'Manrope', fontSize: 8, letterSpacing: 1.3, color: c.muted } }));