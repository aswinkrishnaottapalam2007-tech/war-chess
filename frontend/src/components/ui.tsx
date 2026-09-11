import React from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, Text, TextInput, View, ViewStyle, useWindowDimensions } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { makeStyles, useTheme } from '@/src/theme';

export function Screen({ children, title, eyebrow, right, scroll = true, header = true }: { children: React.ReactNode; title?: string; eyebrow?: string; right?: React.ReactNode; scroll?: boolean; header?: boolean }) {
  const s = useStyles();
  return <SafeAreaView style={s.screen} edges={['top', 'bottom']}><KeyboardAvoidingView style={s.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
    {header && <Header title={title || ''} eyebrow={eyebrow} right={right} />}
    {scroll ? <ScrollView style={s.flex} contentContainerStyle={s.content} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>{children}</ScrollView> : children}
  </KeyboardAvoidingView></SafeAreaView>;
}
export function Header({ title, eyebrow, right }: { title: string; eyebrow?: string; right?: React.ReactNode }) {
  const s = useStyles(), { colors } = useTheme();
  return <View style={s.header}><Pressable testID="back-button" accessibilityLabel="Go back" style={s.iconButton} onPress={() => router.canGoBack() ? router.back() : router.replace('/')}><Ionicons name="arrow-back" size={22} color={colors.onSurface} /></Pressable><View style={s.flex}>{eyebrow && <Text style={s.eyebrow}>{eyebrow}</Text>}<Text testID="screen-title" style={s.headerTitle}>{title}</Text></View>{right}</View>;
}
export function Button({ title, onPress, icon, variant = 'primary', disabled = false, loading = false, testID, compact = false }: { title: string; onPress: () => void; icon?: keyof typeof Ionicons.glyphMap; variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; disabled?: boolean; loading?: boolean; testID: string; compact?: boolean }) {
  const s = useStyles(), { colors } = useTheme();
  const color = variant === 'primary' ? colors.onBrandPrimary : variant === 'danger' ? colors.error : colors.onSurface;
  return <Pressable testID={testID} accessibilityRole="button" disabled={disabled || loading} onPress={onPress} style={({ pressed }) => [s.button, s[variant], compact && s.compact, (disabled || loading) && s.disabled, pressed && s.pressed]}>
    {loading ? <ActivityIndicator color={color} /> : <>{icon && <Ionicons name={icon} size={19} color={color} />}<Text style={[s.buttonText, { color }]}>{title}</Text></>}
  </Pressable>;
}
export function Label({ children, testID }: { children: React.ReactNode; testID?: string }) { const s = useStyles(); return <Text testID={testID} style={s.eyebrow}>{children}</Text>; }
export function Title({ children, testID }: { children: React.ReactNode; testID?: string }) { const s = useStyles(); return <Text testID={testID} style={s.title}>{children}</Text>; }
export function Body({ children, muted = false, testID }: { children: React.ReactNode; muted?: boolean; testID?: string }) { const s = useStyles(); return <Text testID={testID} style={[s.body, muted && s.muted]}>{children}</Text>; }
export function Card({ children, style, testID }: { children: React.ReactNode; style?: ViewStyle; testID?: string }) { const s = useStyles(); return <View testID={testID} style={[s.card, style]}>{children}</View>; }
export function Input({ label, testID, ...props }: React.ComponentProps<typeof TextInput> & { label: string; testID: string }) {
  const s = useStyles(), { colors } = useTheme();
  return <View style={s.field}><Label>{label}</Label><TextInput testID={testID} accessibilityLabel={label} placeholderTextColor={colors.muted} style={s.input} {...props} /></View>;
}
export function Notice({ text, icon = 'information-circle-outline', testID = 'status-notice' }: { text: string; icon?: keyof typeof Ionicons.glyphMap; testID?: string }) {
  const s = useStyles(), { colors } = useTheme(); return <View style={s.notice} testID={testID}><Ionicons name={icon} size={20} color={colors.brand} /><Text style={s.noticeText}>{text}</Text></View>;
}
export function Sheet({ visible, title, onClose, children }: { visible: boolean; title: string; onClose: () => void; children: React.ReactNode }) {
  const s = useStyles(), { colors } = useTheme(), insets = useSafeAreaInsets(), { height } = useWindowDimensions();
  return <Modal visible={visible} transparent animationType={Platform.OS === 'web' ? 'none' : 'slide'} onRequestClose={onClose}><View style={[s.modal, { height, width: '100%' }]}>
    <Pressable accessibilityLabel="Close sheet" testID="sheet-backdrop" style={s.backdrop} onPress={onClose} />
    <KeyboardAvoidingView testID="action-sheet" enabled={Platform.OS !== 'web'} behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={[s.sheet, { height: Math.min(height - insets.top - 20, Math.max(height * 0.78, 540)), paddingBottom: Math.max(insets.bottom, 20) }]}><View style={s.handle} /><View style={s.sheetHeader}><Text style={s.sheetTitle}>{title}</Text><Pressable testID="close-sheet-button" accessibilityLabel="Close" onPress={onClose} style={s.iconButton}><Ionicons name="close" size={24} color={colors.onSurface} /></Pressable></View><ScrollView style={s.sheetScroll} keyboardShouldPersistTaps="handled" contentContainerStyle={s.sheetContent}>{children}</ScrollView></KeyboardAvoidingView>
  </View></Modal>;
}
export function Chips({ items, selected, onSelect }: { items: { id: string; label: string }[]; selected: string; onSelect: (id: string) => void }) {
  const s = useStyles(); return <View style={s.chipRow}><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipContent}>{items.map(item => <Pressable testID={`filter-${item.id}`} key={item.id} onPress={() => onSelect(item.id)} style={[s.chip, selected === item.id && s.chipSelected]}><Text style={[s.chipText, selected === item.id && s.chipTextSelected]}>{item.label}</Text></Pressable>)}</ScrollView></View>;
}
const useStyles = makeStyles(c => ({
  screen: { flex: 1, backgroundColor: c.surface }, flex: { flex: 1 }, content: { paddingHorizontal: 24, paddingTop: 16, paddingBottom: 28, gap: 24, width: '100%', maxWidth: 760, alignSelf: 'center' },
  header: { flexDirection: 'row', gap: 12, alignItems: 'center', paddingHorizontal: 18, paddingVertical: 14, backgroundColor: c.surface, borderBottomWidth: 1, borderBottomColor: c.divider },
  iconButton: { width: 44, height: 44, justifyContent: 'center', alignItems: 'center' }, eyebrow: { fontFamily: 'Manrope', color: c.brand, fontSize: 10, fontWeight: '700', letterSpacing: 2.1, lineHeight: 18 }, headerTitle: { fontFamily: 'Cinzel', fontSize: 19, color: c.onSurface },
  title: { fontFamily: 'Cinzel', fontSize: 31, lineHeight: 41, color: c.onSurface }, body: { fontFamily: 'Manrope', color: c.onSurfaceSecondary, fontSize: 14, lineHeight: 23 }, muted: { color: c.muted },
  button: { minHeight: 56, borderRadius: 8, flexDirection: 'row', justifyContent: 'center', alignItems: 'center', paddingHorizontal: 20, gap: 12, borderWidth: 1 },
  primary: { backgroundColor: c.brandPrimary, borderColor: c.brandPrimary }, secondary: { backgroundColor: c.surfaceSecondary, borderColor: c.border }, ghost: { backgroundColor: c.transparent, borderColor: c.transparent }, danger: { backgroundColor: c.surfaceSecondary, borderColor: c.error },
  buttonText: { fontFamily: 'Manrope', fontSize: 12, fontWeight: '800', letterSpacing: 1.8, textAlign: 'center' }, compact: { minHeight: 44, paddingHorizontal: 14 }, disabled: { opacity: 0.4 }, pressed: { opacity: 0.72, transform: [{ scale: 0.985 }] },
  card: { backgroundColor: c.surfaceSecondary, borderColor: c.border, borderWidth: 1, borderRadius: 12, padding: 20, gap: 12 }, field: { gap: 9 }, input: { minHeight: 56, borderColor: c.border, borderWidth: 1, borderRadius: 8, paddingHorizontal: 16, color: c.onSurface, fontFamily: 'Manrope', fontSize: 15, backgroundColor: c.surfaceSecondary },
  notice: { padding: 15, flexDirection: 'row', alignItems: 'flex-start', gap: 10, backgroundColor: c.brandTertiary, borderRadius: 8 }, noticeText: { flex: 1, fontFamily: 'Manrope', fontSize: 12, lineHeight: 20, color: c.onBrandTertiary },
  modal: { flex: 1, justifyContent: 'flex-end', backgroundColor: c.overlay }, backdrop: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }, sheet: { backgroundColor: c.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, flexShrink: 1, maxHeight: '96%', width: '100%', maxWidth: 760, alignSelf: 'center', borderWidth: 1, borderColor: c.border }, sheetScroll: { flex: 1, minHeight: 0 },
  handle: { width: 36, height: 4, borderRadius: 3, backgroundColor: c.borderStrong, alignSelf: 'center', marginTop: 10 }, sheetHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 24, paddingTop: 12, paddingBottom: 8 }, sheetTitle: { fontFamily: 'Cinzel', fontSize: 22, color: c.onSurface, flex: 1 }, sheetContent: { padding: 24, gap: 20 },
  chipRow: { height: 56, flexShrink: 0 }, chipContent: { gap: 8, paddingHorizontal: 24, alignItems: 'center' }, chip: { flexShrink: 0, height: 36, paddingHorizontal: 17, borderWidth: 1, borderColor: c.border, borderRadius: 18, justifyContent: 'center', backgroundColor: c.surfaceSecondary }, chipSelected: { backgroundColor: c.brandTertiary, borderColor: c.brand }, chipText: { color: c.muted, fontFamily: 'Manrope', fontSize: 12, fontWeight: '600' }, chipTextSelected: { color: c.brand },
}));