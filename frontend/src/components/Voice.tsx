import React, { useState } from 'react';
import { Linking, View } from 'react-native';
import { AudioModule } from 'expo-audio';
import { WebView } from 'react-native-webview';
import { api, BASE_URL } from '@/src/api';
import { Button, Body, Notice } from './ui';
import { makeStyles } from '@/src/theme';

export function Voice({ code }: { code: string }) {
  const [credentials, setCredentials] = useState<any>(null), [message, setMessage] = useState(''), [blocked, setBlocked] = useState(false), [busy, setBusy] = useState(false), [attempts, setAttempts] = useState(0), s = useStyles();
  const connect = async () => { setBusy(true); try {
    const data = await api(`/rooms/${code}/voice`, 'POST');
    let permission = await AudioModule.getRecordingPermissionsAsync();
    if (!permission.granted && (!permission.canAskAgain || attempts >= 2)) { setBlocked(true); setMessage('Enable microphone access in Settings to talk with your alliance.'); return; }
    if (!permission.granted) { setAttempts(attempts + 1); permission = await AudioModule.requestRecordingPermissionsAsync(); }
    if (!permission.granted) { setMessage('Microphone access was declined. Text chat still works.'); setBlocked(!permission.canAskAgain || attempts >= 1); return; }
    setCredentials(data);
  } catch (e: any) { setMessage(e.message); } finally { setBusy(false); } };
  return <View style={s.wrap}>{credentials ? <><WebView testID="voice-webview" source={{ uri: `${BASE_URL}/api/voice-client` }} injectedJavaScript={`window.setVoiceCredentials(${JSON.stringify(credentials)});true;`} originWhitelist={[BASE_URL]} mediaPlaybackRequiresUserAction={false} allowsInlineMediaPlayback style={s.webview} /><Button testID="disconnect-voice-button" title="LEAVE VOICE" variant="secondary" onPress={() => setCredentials(null)} /></> : <><Body>Talk through the next move.</Body><Body muted>Voice is recommended for fast coordination. Your microphone is only used after you join. Text chat stays available if you prefer it.</Body>{!!message && <Notice text={message} testID="voice-status" />}{blocked ? <Button testID="voice-open-settings-button" title="OPEN SETTINGS" onPress={() => Linking.openSettings()} /> : <Button testID="join-voice-button" title="ENABLE MICROPHONE & JOIN" icon="mic-outline" loading={busy} onPress={connect} />}</>}</View>;
}
const useStyles = makeStyles(c => ({ wrap: { gap: 20, minHeight: 260 }, webview: { height: 320, backgroundColor: c.surfaceSecondary } }));