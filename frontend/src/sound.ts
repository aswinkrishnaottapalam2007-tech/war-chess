import { useCallback } from 'react';
import { useAudioPlayer } from 'expo-audio';
import * as Speech from 'expo-speech';
import { useApp } from '@/src/context';

export function useSound() {
  const { volume } = useApp();
  const move = useAudioPlayer(require('../assets/audio/move.wav'));
  const capture = useAudioPlayer(require('../assets/audio/capture.wav'));
  const notice = useAudioPlayer(require('../assets/audio/notice.wav'));
  return useCallback((kind: string, announcement?: string) => {
    if (volume <= 0) return;
    const player = kind === 'move' ? move : kind === 'capture' ? capture : notice;
    try { player.volume = volume; player.seekTo(0); player.play(); } catch {}
    if (announcement) Speech.speak(announcement, { language: 'en-US', rate: 0.85, pitch: 0.85, volume });
  }, [volume, move, capture, notice]);
}