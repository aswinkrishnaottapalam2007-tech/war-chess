import React, { useState } from 'react';
import { router } from 'expo-router';
import { api } from '@/src/api';
import { useApp } from '@/src/context';
import { Body, Button, Input, Notice, Sheet } from './ui';

export function DeleteAccount() {
  const [open, setOpen] = useState(false), [password, setPassword] = useState(''), [confirmation, setConfirmation] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const { signOut, notify } = useApp();
  const remove = async () => {
    setBusy(true); setError('');
    try { const result = await api('/auth/delete-account', 'POST', { password, confirmation }); await signOut(); setOpen(false); router.replace('/'); notify(result.deleted ? 'Your account has been deleted.' : 'Your deletion request is accepted. Cleanup will finish automatically.'); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  return <><Button testID="delete-account-button" title="DELETE ACCOUNT" variant="danger" onPress={() => { setOpen(true); setError(''); setPassword(''); setConfirmation(''); }} /><Sheet visible={open} title="Delete your account?" onClose={() => { if (!busy) setOpen(false); }}><Notice text="This is permanent. Your login, sessions, submitted chat messages, and personal leaderboard entries will be removed. Active matches will mark your commander as having left." /><Body>Confirm your password and type DELETE to continue.</Body><Input testID="delete-password-input" label="CURRENT PASSWORD" secureTextEntry autoCapitalize="none" value={password} onChangeText={setPassword} /><Input testID="delete-confirmation-input" label="TYPE DELETE" autoCapitalize="characters" value={confirmation} onChangeText={setConfirmation} />{!!error && <Notice testID="delete-account-error" text={error} />}<Button testID="confirm-delete-account-button" title="PERMANENTLY DELETE ACCOUNT" variant="danger" disabled={confirmation !== 'DELETE' || password.length < 8} loading={busy} onPress={remove} /><Button testID="cancel-delete-account-button" title="KEEP MY ACCOUNT" variant="secondary" disabled={busy} onPress={() => setOpen(false)} /></Sheet></>;
}