import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Screen, Button, Input, Title, Body, Label, Notice } from '@/src/components/ui';
import { Piece } from '@/src/components/Piece';
import { makeStyles, useTheme } from '@/src/theme';
import { useApp } from '@/src/context';
import { api } from '@/src/api';

export default function Auth() {
  const [register, setRegister] = useState(false), [name, setName] = useState(''), [email, setEmail] = useState(''), [password, setPassword] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState(''), [showPassword, setShowPassword] = useState(false);
  const { signIn } = useApp(), s = useStyles(), { colors } = useTheme();
  const submit = async () => {
    setError(''); if (!email.trim() || password.length < 8 || (register && name.trim().length < 2)) { setError('Enter a valid email, a password of at least 8 characters, and your commander name.'); return; }
    setBusy(true); try { const data = await api(`/auth/${register ? 'register' : 'login'}`, 'POST', { email: email.trim(), password, ...(register ? { name: name.trim() } : {}) }); await signIn(data); router.replace('/join'); } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };
  return <Screen title="The war room" eyebrow="WAR CHESS"><View style={s.intro}><View style={s.crest}><Piece role="king" size={64} /></View><Label>YOUR ALLIANCE AWAITS</Label><Title>{register ? 'Take your place.' : 'Welcome, commander.'}</Title><Body muted>{register ? 'Create your account and become part of something greater.' : 'Sign in to join your team and defend the kingdom.'}</Body></View>
    <View style={s.switcher}>{['SIGN IN', 'CREATE ACCOUNT'].map((text, i) => <Pressable testID={i === 0 ? 'sign-in-tab' : 'create-account-tab'} key={text} onPress={() => { setRegister(i === 1); setError(''); }} style={[s.tab, register === (i === 1) && s.activeTab]}><Text style={[s.tabText, register === (i === 1) && s.activeText]}>{text}</Text></Pressable>)}</View>
    {register && <Input testID="auth-name-input" label="COMMANDER NAME" placeholder="How should your team call you?" value={name} onChangeText={setName} maxLength={24} autoComplete="nickname" />}
    <Input testID="auth-email-input" label="EMAIL ADDRESS" placeholder="you@example.com" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
    <View style={s.password}><Input testID="auth-password-input" label="PASSWORD" placeholder="At least 8 characters" value={password} onChangeText={setPassword} secureTextEntry={!showPassword} autoComplete={register ? 'new-password' : 'current-password'} onSubmitEditing={submit} /><Pressable testID="toggle-password-button" accessibilityLabel="Show or hide password" onPress={() => setShowPassword(!showPassword)} style={s.eye}><Ionicons name={showPassword ? 'eye-off-outline' : 'eye-outline'} size={20} color={colors.muted} /></Pressable></View>
    {!!error && <Notice text={error} testID="auth-error" />}
    <Button testID="auth-submit-button" title={register ? 'CREATE ACCOUNT' : 'ENTER THE WAR ROOM'} onPress={submit} loading={busy} icon="arrow-forward" />
    <View style={s.security}><Ionicons name="shield-checkmark-outline" size={16} color={colors.muted} /><Text style={s.securityText}>Your account. Your roles. Your legacy.</Text></View>
  </Screen>;
}
const useStyles = makeStyles(c => ({ intro: { gap: 12, paddingTop: 14 }, crest: { width: 80, height: 80, borderWidth: 1, borderColor: c.borderStrong, borderRadius: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: c.brandTertiary, marginBottom: 8 }, switcher: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: c.border }, tab: { flex: 1, alignItems: 'center', paddingVertical: 16, borderBottomWidth: 2, borderBottomColor: c.transparent }, activeTab: { borderBottomColor: c.brand }, tabText: { fontFamily: 'Manrope', fontSize: 10, fontWeight: '800', letterSpacing: 1.4, color: c.muted }, activeText: { color: c.brand }, password: { position: 'relative' }, eye: { position: 'absolute', bottom: 6, right: 6, width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }, security: { flexDirection: 'row', gap: 8, justifyContent: 'center' }, securityText: { fontFamily: 'Manrope', color: c.muted, fontSize: 11 } }));