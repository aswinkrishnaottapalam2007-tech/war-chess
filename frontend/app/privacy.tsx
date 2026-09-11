import React from 'react';
import { Body, Card, Label, Screen, Title } from '@/src/components/ui';

export default function Privacy() {
  return <Screen title="Privacy & voice" eyebrow="CHAOS ENGINE STUDIO"><Title>Your alliance. Your privacy.</Title>
    <Card><Label>ACCOUNT & GAME DATA</Label><Body>WAR CHESS stores your email, commander name, password hash, account sessions, room membership, game moves, and match statistics to operate multiplayer games. Your password is hashed; it is not stored as readable text.</Body></Card>
    <Card><Label>TEXT & PUBLIC RANKINGS</Label><Body>Team chat is visible to members of its room. Recent messages and game history are stored on the server. Public role leaderboards show commander names and aggregate statistics, not email addresses or internal account IDs.</Body></Card>
    <Card><Label>LIVE VOICE</Label><Body>Microphone access starts only when you choose Join voice. Audio travels encrypted in transit through the game server to your current alliance. It is relayed in temporary memory, not recorded or stored in the database. It is not end-to-end encrypted.</Body><Body>Voice is foreground-only. It stops when you leave voice, leave the match, sign out, or background the app. Other players may independently record what they hear; avoid sharing sensitive information.</Body></Card>
    <Card><Label>YOUR CONTROLS</Label><Body>Mute or leave voice at any time. Revoke microphone permission in device settings and keep using text chat. Change sound volume and theme in Settings. Delete your account in Settings with password confirmation to remove your login, submitted chat, personal statistics, and active sessions; non-personal match history may remain for the other players.</Body></Card>
    <Card><Label>DEVICE STORAGE & CONNECTIONS</Label><Body>Your device stores your session and display preferences. Native sessions use the platform secure-storage adapter. Browser sessions use browser storage. The studio opening is bundled with the app, and artwork may be loaded from managed asset hosting. Connection metadata may be processed to enforce abuse limits and investigate service failures.</Body></Card>
  </Screen>;
}