import React, { useEffect, useMemo } from 'react';
import { Pressable, Text, View, useWindowDimensions } from 'react-native';
import Animated, { useSharedValue, useAnimatedStyle, withTiming, withSequence, Easing } from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import { Piece } from './Piece';
import { makeStyles, useTheme } from '@/src/theme';
import { Role, Room } from '@/src/types';

const roleMap: Record<string, Role> = { k: 'king', q: 'queen', r: 'rook', b: 'bishop', n: 'knight', p: 'pawn' };
type BoardPiece = { id: string; role: Role; enemy: boolean; square: string };
function buildPieces(moves: string[]) {
  const pieces: Record<string, BoardPiece> = {};
  ['rnbqkbnr', 'pppppppp', '', '', '', '', 'PPPPPPPP', 'RNBQKBNR'].forEach((rank, y) => [...rank].forEach((ch, x) => { const square = `${'abcdefgh'[x]}${8 - y}`; pieces[square] = { id: square, role: roleMap[ch.toLowerCase()], enemy: ch === ch.toLowerCase(), square }; }));
  moves.forEach(uci => {
    const from = uci.slice(0, 2), to = uci.slice(2, 4), piece = pieces[from];
    if (!piece) return;
    if (piece.role === 'pawn' && from[0] !== to[0] && !pieces[to]) delete pieces[`${to[0]}${from[1]}`];
    if (piece.role === 'king' && Math.abs(from.charCodeAt(0) - to.charCodeAt(0)) === 2) {
      const rookFrom = `${to[0] === 'g' ? 'h' : 'a'}${from[1]}`, rookTo = `${to[0] === 'g' ? 'f' : 'd'}${from[1]}`;
      if (pieces[rookFrom]) { pieces[rookTo] = { ...pieces[rookFrom], square: rookTo }; delete pieces[rookFrom]; }
    }
    pieces[to] = { ...piece, square: to, role: uci[4] ? roleMap[uci[4]] : piece.role }; delete pieces[from];
  });
  return Object.values(pieces);
}
function MovingPiece({ piece, cell, jump }: { piece: BoardPiece; cell: number; jump: boolean }) {
  const x = (piece.square.charCodeAt(0) - 97) * cell, y = (8 - Number(piece.square[1])) * cell;
  const px = useSharedValue(x), py = useSharedValue(y), lift = useSharedValue(0);
  useEffect(() => { const changed = px.value !== x || py.value !== y; px.value = withTiming(x, { duration: 420, easing: Easing.inOut(Easing.cubic) }); py.value = withTiming(y, { duration: 420, easing: Easing.inOut(Easing.cubic) }); if (jump && changed) lift.value = withSequence(withTiming(-cell * 0.65, { duration: 190 }), withTiming(0, { duration: 230 })); }, [x, y, cell, jump, lift, px, py]);
  const animated = useAnimatedStyle(() => ({ transform: [{ translateX: px.value }, { translateY: py.value + lift.value }, { scale: 1 + Math.abs(lift.value) / (cell * 5) }] }));
  const s = useStyles();
  return <Animated.View style={[s.piece, { width: cell, height: cell, pointerEvents: 'none' }, animated]}><Piece role={piece.role} enemy={piece.enemy} size={cell * 0.93} /></Animated.View>;
}
export function Board({ room, selected, onSquare }: { room: Room; selected: string | null; onSquare: (square: string) => void }) {
  const { width } = useWindowDimensions(), s = useStyles(), { colors: c } = useTheme();
  const cell = Math.floor(Math.min(width - 36, 552) / 8), size = cell * 8;
  const pieces = useMemo(() => buildPieces(room.moves), [room.moves]);
  const legal = new Set(room.legal_moves.filter(m => m.startsWith(selected || '---')).map(m => m.slice(2, 4)));
  return <View testID="chess-board" style={s.outer}><View style={[s.fileLabels, { width: size }]}>{[...'abcdefgh'].map(file => <Text key={file} style={[s.coordinate, { width: cell }]}>{file}</Text>)}</View>
    <LinearGradient colors={[c.pieceLight, c.boardFrame, c.pieceDark]} style={s.frame}><View style={[s.board, { width: size, height: size }]}>
      {Array.from({ length: 64 }, (_, i) => { const x = i % 8, y = Math.floor(i / 8), square = `${'abcdefgh'[x]}${8 - y}`, isSelected = selected === square, last = room.last_move?.from === square || room.last_move?.to === square;
        return <Pressable testID={`square-${square}`} accessibilityLabel={`${square}${room.owners[square] ? ` ${room.owners[square]}` : ''}`} key={square} onPress={() => onSquare(square)} style={({ pressed, hovered }: any) => [s.square, { width: cell, height: cell, backgroundColor: (x + y) % 2 ? c.squareB : c.squareA }, last && s.lastSquare, (isSelected || pressed || hovered) && s.selectedSquare]}>{x === 0 && <Text style={s.rank}>{8 - y}</Text>}{legal.has(square) && <View style={pieces.find(p => p.square === square) ? s.captureIndicator : s.legalIndicator} />}</Pressable>; })}
      {pieces.map(p => <MovingPiece key={`${room.round_id}-${p.id}`} piece={p} cell={cell} jump={room.last_move?.to === p.square && room.last_move?.jump === true} />)}
    </View></LinearGradient><View style={[s.fileLabels, { width: size }]}>{[...'abcdefgh'].map(file => <Text key={file} style={[s.coordinate, { width: cell }]}>{file}</Text>)}</View></View>;
}
const useStyles = makeStyles(c => ({ outer: { alignItems: 'center', width: '100%' }, frame: { padding: 3, borderRadius: 4 }, board: { flexDirection: 'row', flexWrap: 'wrap', overflow: 'hidden', position: 'relative', borderRadius: 2 }, square: { alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: c.transparent }, lastSquare: { borderColor: c.brand, backgroundColor: c.boardFrame }, selectedSquare: { backgroundColor: c.glow, borderColor: c.pieceLight }, piece: { position: 'absolute', top: 0, left: 0, alignItems: 'center', justifyContent: 'center' }, fileLabels: { flexDirection: 'row', height: 23, alignItems: 'center' }, coordinate: { textAlign: 'center', fontFamily: 'Manrope', fontSize: 9, color: c.muted }, rank: { position: 'absolute', left: 2, top: 2, color: c.muted, fontSize: 8 }, legalIndicator: { width: 11, height: 11, borderRadius: 6, backgroundColor: c.glow }, captureIndicator: { position: 'absolute', width: '90%', height: '90%', borderRadius: 50, borderWidth: 3, borderColor: c.glow } }));