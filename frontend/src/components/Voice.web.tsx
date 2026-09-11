import React, { useEffect, useRef, useState } from 'react';
import { View } from 'react-native';
import { api } from '@/src/api';
import { Button, Body, Label, Notice } from './ui';
import { makeStyles } from '@/src/theme';

export function Voice({ code }: { code: string }) {
  const room = useRef<any>(null), [status, setStatus] = useState(''), [connected, setConnected] = useState(false), [muted, setMuted] = useState(false), [busy, setBusy] = useState(false), [names, setNames] = useState(''), [blocked, setBlocked] = useState(false), s = useStyles();
  useEffect(() => () => { room.current?.disconnect(); }, []);
  const connect = async () => { setBusy(true); setStatus(''); try {
    const data = await api(`/rooms/${code}/voice`, 'POST');
    if (navigator.permissions) { const p = await navigator.permissions.query({ name: 'microphone' as PermissionName }); if (p.state === 'denied') { setBlocked(true); throw new Error('Microphone is blocked. Open your browser’s site settings to allow microphone access. Text chat is still available.'); } }
    const { Room, RoomEvent, Track } = await import('livekit-client');
    const r = new Room(); room.current = r;
    r.on(RoomEvent.TrackSubscribed, track => { if (track.kind === Track.Kind.Audio) document.body.appendChild(track.attach()); });
    r.on(RoomEvent.TrackUnsubscribed, track => track.detach().forEach(el => el.remove()));
    const update = () => setNames([r.localParticipant.name, ...Array.from(r.remoteParticipants.values()).map(p => p.name)].join(' · '));
    r.on(RoomEvent.ParticipantConnected, update); r.on(RoomEvent.ParticipantDisconnected, update);
    r.on(RoomEvent.Reconnecting, () => setStatus('Reconnecting to voice…')); r.on(RoomEvent.Reconnected, () => setStatus('Connected to team voice.'));
    await r.connect(data.server_url, data.participant_token); await r.startAudio(); await r.localParticipant.setMicrophoneEnabled(true); setConnected(true); setMuted(false); setStatus('Connected to team voice.'); update();
  } catch (e: any) { setStatus(e.message); room.current?.disconnect(); } finally { setBusy(false); } };
  return <View style={s.wrap}><Body>Talk through the next move.</Body><Body muted>Voice is recommended for faster coordination. Join to allow microphone access; mute or leave at any time.</Body>{!!status && <Notice testID="voice-status" text={status} />}{connected ? <><Label>IN VOICE: {names}</Label><Button testID="mute-voice-button" title={muted ? 'UNMUTE MICROPHONE' : 'MUTE MICROPHONE'} onPress={async () => { try { await room.current.localParticipant.setMicrophoneEnabled(muted); setMuted(!muted); } catch (e: any) { setStatus(e.message); } }} /><Button testID="disconnect-voice-button" title="LEAVE VOICE" variant="secondary" onPress={async () => { await room.current?.disconnect(); setConnected(false); setStatus('You left voice. Text chat is still available.'); }} /></> : <Button testID="join-voice-button" title={blocked ? 'RETRY AFTER ALLOWING MICROPHONE' : 'ENABLE MICROPHONE & JOIN'} icon="mic-outline" loading={busy} onPress={connect} />}</View>;
}
const useStyles = makeStyles(c => ({ wrap: { gap: 20, minHeight: 260, backgroundColor: c.surface } }));