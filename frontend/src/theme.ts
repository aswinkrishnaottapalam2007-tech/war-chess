import { useMemo, useSyncExternalStore } from 'react';
import { StyleSheet } from 'react-native';
import { storage } from '@/src/utils/storage';

export type ColorScheme = 'dark' | 'light';
const dark = {
  surface: '#0B0E0D', onSurface: '#F1EEE6', surfaceSecondary: '#141917', onSurfaceSecondary: '#E8E6DF',
  surfaceTertiary: '#1C231F', onSurfaceTertiary: '#BEC4B9', surfaceInverse: '#ECE8DC', onSurfaceInverse: '#101510', muted: '#939D92',
  brand: '#CDB078', onBrand: '#171A12', brandPrimary: '#D5B97C', onBrandPrimary: '#151A12',
  brandSecondary: '#322E23', onBrandSecondary: '#E5C990', brandTertiary: '#211F18', onBrandTertiary: '#CFB680',
  success: '#91B89B', onSuccess: '#0E2113', warning: '#E5BD79', onWarning: '#251B0A', error: '#E4978E', onError: '#29100D', info: '#93B9D0', onInfo: '#10202B',
  border: '#2B322B', borderStrong: '#77633E', divider: '#222921', transparent: 'transparent',
  overlay: '#000000B8', glow: '#FFFFFF75', squareA: '#44473F', squareB: '#383D35', boardFrame: '#A58B56',
  pieceLight: '#F3D9A0', pieceMid: '#C3A05B', pieceDark: '#765A30', enemyLight: '#798378', enemyMid: '#343D36', enemyDark: '#131C17',
  heroFade: '#0B0E0D00', heroText: '#F2EBDD', heroMuted: '#BDB7A8', heroBackground: '#0B0E0D',
};
const light: typeof dark = {
  surface: '#F5F8FA', onSurface: '#1B3444', surfaceSecondary: '#FFFFFF', onSurfaceSecondary: '#294858',
  surfaceTertiary: '#EAF1F6', onSurfaceTertiary: '#4E687B', surfaceInverse: '#24485E', onSurfaceInverse: '#FFFFFF', muted: '#617B8B',
  brand: '#387EA5', onBrand: '#FFFFFF', brandPrimary: '#A9D4EE', onBrandPrimary: '#183D56',
  brandSecondary: '#DDEEF8', onBrandSecondary: '#285E7D', brandTertiary: '#E8F3F9', onBrandTertiary: '#39789B',
  success: '#397854', onSuccess: '#FFFFFF', warning: '#9D681F', onWarning: '#FFFFFF', error: '#B64440', onError: '#FFFFFF', info: '#367DA4', onInfo: '#FFFFFF',
  border: '#D8E3EB', borderStrong: '#88B3CF', divider: '#E1EAF0', transparent: 'transparent',
  overlay: '#102837A8', glow: '#FFFFFFD0', squareA: '#D8E5ED', squareB: '#C3D5E1', boardFrame: '#8DADBF',
  pieceLight: '#FFFFFF', pieceMid: '#C5DEEC', pieceDark: '#6F9CB7', enemyLight: '#6386A0', enemyMid: '#355870', enemyDark: '#18364B',
  heroFade: '#0B0E0D00', heroText: '#F2EBDD', heroMuted: '#BDB7A8', heroBackground: '#0B0E0D',
};
export type ThemeColors = typeof dark;
export const themes = { dark, light };
export const defaultScheme: ColorScheme = 'dark';
let active: ColorScheme = 'dark';
const listeners = new Set<() => void>();
export function setColorScheme(value: ColorScheme | null) {
  active = value || 'dark';
  storage.setItem('war-theme', active);
  listeners.forEach(fn => fn());
}
export async function restoreTheme() {
  const saved = await storage.getItem<string>('war-theme', 'dark');
  if (saved === 'light' || saved === 'dark') setColorScheme(saved);
}
export function useTheme() {
  const scheme = useSyncExternalStore(fn => { listeners.add(fn); return () => { listeners.delete(fn); }; }, () => active, () => 'dark' as ColorScheme);
  return { scheme, colors: themes[scheme] };
}
export function makeStyles<T extends StyleSheet.NamedStyles<T>>(factory: (c: ThemeColors) => T): () => T {
  return () => { const { colors } = useTheme(); return useMemo(() => StyleSheet.create(factory(colors)), [colors]); };
}