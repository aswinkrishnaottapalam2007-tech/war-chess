import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useVideoPlayer, VideoView } from 'expo-video';
import { StatusBar } from 'expo-status-bar';
import { useApp } from '@/src/context';
import { makeStyles, useTheme } from '@/src/theme';

import { studioSource } from './studioSource';

export function StudioIntro({ onDone }: { onDone: () => void }) {
  const s = useStyles(), { colors: c } = useTheme(), { volume } = useApp();
  const finished = useRef(false), view = useRef<VideoView>(null), [muted, setMuted] = useState(Platform.OS === 'web'), [loading, setLoading] = useState(true);
  const player = useVideoPlayer(studioSource, p => { p.loop = false; p.muted = Platform.OS === 'web' || volume === 0; p.volume = volume; });
  const finish = useCallback(() => { if (finished.current) return; finished.current = true; try { player.pause(); } catch {} onDone(); }, [onDone, player]);
  const play = useCallback(() => {
    if (finished.current) return;
    if (Platform.OS === 'web') {
      // The SDK's web play() discards the HTML playback promise. Handle expected
      // cancellation when Skip/unmount interrupts loading, rather than leaking it.
      const element = (view.current as any)?.nativeRef?.current as HTMLVideoElement | undefined;
      element?.play().catch(error => { if (!finished.current && error.name !== 'AbortError') finish(); });
    } else player.play();
  }, [player, finish]);
  useEffect(() => {
    const ended = player.addListener('playToEnd', finish);
    const status = player.addListener('statusChange', event => { if (event.status === 'readyToPlay') { setLoading(false); play(); } if (event.status === 'error') finish(); });
    // Expo web's setup callback runs before VideoView is attached; play after commit.
    play();
    // A failed decoder or slow source can never trap the player on the studio screen.
    const timeout = setTimeout(finish, 20000);
    return () => { ended.remove(); status.remove(); clearTimeout(timeout); };
  }, [player, finish, play]);
  useEffect(() => { player.volume = volume; player.muted = muted || volume === 0; }, [volume, muted, player]);
  return <SafeAreaView testID="studio-opening" style={s.screen} edges={['top', 'bottom']}><StatusBar style="light" /><View style={s.top}><Text style={s.studioLabel}>CHAOS ENGINE STUDIO</Text><Pressable testID="skip-intro-button" accessibilityLabel="Skip studio opening" onPress={finish} style={({ pressed }) => [s.skip, pressed && s.pressed]}><Text style={s.skipText}>SKIP INTRO</Text><Ionicons name="play-skip-forward-outline" color={c.studioText} size={16} /></Pressable></View>
    <View testID="studio-video" style={s.stage}><VideoView ref={view} player={player} style={s.video} contentFit="contain" nativeControls={false} allowsPictureInPicture={false} playsInline />{loading && <ActivityIndicator testID="intro-loading" color={c.studioText} style={s.spinner} />}</View>
    <View style={s.bottom}><Text style={s.presents}>P R E S E N T S</Text><Text style={s.game}>WAR CHESS</Text><Pressable testID="intro-sound-button" accessibilityLabel={muted ? 'Enable intro sound' : 'Mute intro sound'} disabled={volume === 0} onPress={() => setMuted(!muted)} style={s.sound}><Ionicons name={muted || volume === 0 ? 'volume-mute-outline' : 'volume-medium-outline'} size={19} color={c.studioMuted} /><Text style={s.soundText}>{muted || volume === 0 ? 'SOUND OFF' : 'SOUND ON'}</Text></Pressable></View>
  </SafeAreaView>;
}
const useStyles = makeStyles(c => ({ screen: { flex: 1, backgroundColor: c.studioBackground }, top: { paddingHorizontal: 20, paddingVertical: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }, studioLabel: { fontFamily: 'Manrope', fontSize: 8, letterSpacing: 1.3, color: c.studioMuted, flexShrink: 1 }, skip: { minHeight: 44, paddingHorizontal: 13, borderWidth: 1, borderColor: c.studioBorder, borderRadius: 22, alignItems: 'center', flexDirection: 'row', gap: 8 }, skipText: { fontFamily: 'Manrope', color: c.studioText, fontSize: 9, letterSpacing: 1 }, stage: { flex: 1, position: 'relative' }, video: { width: '100%', height: '100%' }, spinner: { position: 'absolute', alignSelf: 'center', top: '50%' }, bottom: { alignItems: 'center', paddingTop: 20, paddingBottom: 30, gap: 12 }, presents: { fontFamily: 'Manrope', color: c.studioMuted, fontSize: 9 }, game: { fontFamily: 'Cinzel', color: c.studioText, fontSize: 25, letterSpacing: 4 }, sound: { flexDirection: 'row', gap: 8, minHeight: 44, alignItems: 'center', paddingHorizontal: 16 }, soundText: { fontFamily: 'Manrope', color: c.studioMuted, fontSize: 9, letterSpacing: 1 }, pressed: { opacity: 0.6 } }));