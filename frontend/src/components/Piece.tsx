import React, { useId } from 'react';
import Svg, { Defs, LinearGradient, Stop, Path, Ellipse, G } from 'react-native-svg';
import { useTheme } from '@/src/theme';
import { Role } from '@/src/types';

const paths: Record<Role, string> = {
  pawn: 'M21 18a7 7 0 1 0 14 0a7 7 0 1 0-14 0 M23 25h10l-2 7 5 9H20l5-9z M19 42h18v4H19z',
  rook: 'M15 10h7v6h4v-6h5v6h4v-6h7v14H15z M19 25h19l-3 16H22z M19 41h19v5H19z',
  bishop: 'M28 7C17 17 15 23 22 28h12c7-5 5-11-6-21z M24 28h8l-1 6 6 8H19l6-8z M18 42h20v4H18z',
  knight: 'M18 41c-1-10 3-14 12-20l-6-2-7 6-7-5L22 7l1-5 7 5c10 0 15 15 11 24l-5 10z M17 42h22v4H17z',
  queen: 'M15 15l7 6 6-12 6 12 7-6-5 16H20z M21 32h14l-3 7 6 4H18l6-4z M18 43h20v3H18z',
  king: 'M26 3h4v5h5v4h-5v5h-4v-5h-5V8h5z M18 19c0-5 7-5 10 0 3-5 10-5 10 0 0 5-4 8-5 11H23c-1-3-5-6-5-11z M23 31h10l-2 7 6 5H19l6-5z M18 43h20v3H18z',
};
export function Piece({ role, size = 52, enemy = false, testID }: { role: Role; size?: number; enemy?: boolean; testID?: string }) {
  const { colors: c } = useTheme(), raw = useId(), id = raw.replace(/:/g, '');
  return <Svg testID={testID} width={size} height={size} viewBox="0 0 56 56"><Defs><LinearGradient id={id} x1="0" y1="0" x2="1" y2="0"><Stop offset="0" stopColor={enemy ? c.enemyDark : c.pieceDark} /><Stop offset="0.33" stopColor={enemy ? c.enemyLight : c.pieceLight} /><Stop offset="0.56" stopColor={enemy ? c.enemyMid : c.pieceMid} /><Stop offset="0.79" stopColor={enemy ? c.enemyLight : c.pieceLight} /><Stop offset="1" stopColor={enemy ? c.enemyDark : c.pieceDark} /></LinearGradient></Defs>
    <Ellipse cx="28" cy="49" rx="18" ry="4" fill={c.overlay} /><G fill={`url(#${id})`} stroke={enemy ? c.enemyLight : c.pieceLight} strokeWidth="0.7" strokeLinejoin="round"><Path d={paths[role]} /><Path d="M16 47h24l3 4H13z" />{role === 'bishop' && <Path d="M30 12l-5 10" fill="none" stroke={c.pieceDark} strokeWidth="2" />}{role === 'knight' && <Ellipse cx="25" cy="13" rx="1.3" ry="1.3" fill={c.enemyDark} />}{role === 'queen' && <><Ellipse cx="15" cy="14" rx="2" ry="2" /><Ellipse cx="28" cy="8" rx="2" ry="2" /><Ellipse cx="41" cy="14" rx="2" ry="2" /></>}</G>
  </Svg>;
}