import { createContext, useContext } from 'react';
import type { VoiceSnapshot } from './transport';
export const idleVoice: VoiceSnapshot = { status: 'idle', message: '', peers: [], muted: false, receivedFrames: 0 };
export type VoiceController = VoiceSnapshot & { code: string | null; blocked: boolean; join: (code: string) => Promise<void>; leave: () => void; toggleMute: () => void };
export const VoiceContext = createContext<VoiceController>(null as any);
export const useVoice = () => useContext(VoiceContext);