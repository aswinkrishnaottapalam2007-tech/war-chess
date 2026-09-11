export const ROLES = ['king', 'queen', 'rook', 'bishop', 'knight', 'pawn'] as const;
export type Role = typeof ROLES[number];
export const ROLE_DETAILS: Record<Role, { title: string; subtitle: string; description: string }> = {
  king: { title: 'King', subtitle: 'THE COMMANDER', description: 'Lead the team. Approve commands. Protect the kingdom.' },
  queen: { title: 'Queen', subtitle: 'THE SOVEREIGN', description: 'Move freely. Seek the King’s approval to capture.' },
  rook: { title: 'Rook', subtitle: 'THE STRONGHOLD', description: 'Command both rooks. Hold the lines and break through.' },
  bishop: { title: 'Bishop', subtitle: 'THE TACTICIAN', description: 'Control the diagonals. See what others cannot.' },
  knight: { title: 'Knight', subtitle: 'THE VANGUARD', description: 'Leap over the front line. Strike from the unexpected.' },
  pawn: { title: 'Pawn', subtitle: 'THE LEGION', description: 'Eight pieces. Complete freedom. The power to bring allies back.' },
};
export const DIFFICULTIES = [
  { id: 'easy', name: 'Easy', tag: 'FIND YOUR FOOTING', description: 'A gentler opponent. Learn to command together.', level: 1 },
  { id: 'hard', name: 'Hard', tag: 'A WORTHY ADVERSARY', description: 'Sharper tactics. Every decision matters.', level: 2 },
  { id: 'extreme', name: 'Extreme', tag: 'NO ROOM FOR ERROR', description: 'Deep calculation. Unforgiving precision.', level: 3 },
  { id: 'regret', name: 'Maybe you will regret', tag: 'ENTER AT YOUR OWN RISK', description: 'Maximum practical Stockfish strength. Stand together.', level: 4 },
];
export interface User { id: string; email: string; name: string }
export interface Player { id: string; name: string; role: Role; ready: boolean; connected: boolean; state: 'active' | 'eliminated' | 'spectating' | 'left' }
export interface GameEvent { id: string; type: string; message: string; at: number; captured?: string }
export interface Approval { id: string; role: Role; uci: string; san: string; capture: boolean; user_id: string }
export interface Room {
  code: string; host_id: string; difficulty: string; status: string; phase: string; players: Partial<Record<Role, Player>>;
  revision: number; round_id: string; fen: string; owners: Record<string, Role>; moves: string[]; human_moves: number; command_count: number;
  position_version: number; legal_moves: string[]; server_time: number; deadline: number | null; in_check: boolean; approvals: Approval[];
  events: GameEvent[]; chat: { id: string; user_id: string; name: string; role: Role | null; text: string; at: number }[];
  history: { san: string; uci: string; actor: string; capture: boolean }[];
  last_move: { from: string; to: string; piece: string; san: string; capture: boolean; jump: boolean; actor: string } | null;
  promotion: { square: string; role: Role; expires: number } | null; draw_notice: string | null;
  votes: Record<string, boolean>; restart_requested: boolean; result: string | null; result_reason: string | null; engine_error?: string;
}