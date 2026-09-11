# WAR CHESS

Six commanders. One kingdom. An authoritative cooperative chess game for Expo iOS/Android, with an adaptive browser preview.

## Structure
```
backend/
  server.py          FastAPI routes, authenticated WebSocket, voice tokens
  auth.py            Argon2 credentials and persisted revocable sessions
  database.py        Environment-based Mongo connection
  rules.py           Pure chess/War Chess rules and ownership transitions
  game_service.py    Mongo leases, synchronization, timers, AI orchestration
  engine.py          Bounded Stockfish UCI searches, four strength profiles
  voice_relay.py     Credential-free authenticated live audio fan-out
  realtime.py        Revocable connections and distributed admission limits
  voice.html         Foreground native WebView audio host
frontend/
  app/               Expo Router screens
  src/components/    Board, pieces, lobby, chat, command panels, UI primitives
  src/theme.ts       Whole-app dark/light tokens
  src/useRoom.ts     Realtime state, reconnection, HTTP fallback
  src/utils/storage/ Platform-specific secure/session storage
  assets/            Fonts and original sound samples
memory/PRD.md        Requirements, progress, remaining validation
```

## Development
Use the versions in `frontend/package.json` (Expo 57). Python 3.11+, MongoDB, and an installed Stockfish executable are required. Secrets belong in local environment files, never source control.

Backend environment: see `backend/.env.example`. `MONGO_URL` and `DB_NAME` are required. Optional `STOCKFISH_PATH` overrides executable discovery and must reference an installed executable. Without an explicit path, the backend first uses an installed Stockfish, then bootstraps pinned Debian Stockfish 15.1-4 for Linux arm64/amd64 if necessary. The bootstrap verifies both package and executable SHA-256 hashes, checks a real UCI startup handshake, and writes atomically to a writable cache without root privileges. A first cold start requires HTTPS access to the pinned Debian artifact and a Debian-compatible runtime (glibc >= 2.34, libstdc++6 >= 12); set `STOCKFISH_CACHE_DIR` to customize caching or provision your own engine to avoid startup downloads. Unsupported platforms require an installed Stockfish. CORS is explicitly configured in backend/.env with bearer authentication and cookies disabled; it may be narrowed to known browser origins where appropriate.

```
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001
```

```
cd frontend
yarn install
# EXPO_PUBLIC_BACKEND_URL must be the public HTTPS API origin.
yarn start
```

Do not modify the managed Metro configuration or packager proxy variables. Expo configuration reads the backend origin into `Constants.expoConfig.extra`.

## Play flow
Create six separate accounts. One creates a room, shares the six-letter code, and chooses a difficulty. Each account joins and locks exactly one unique role. All six ready up; the backend starts the match. No artificial teammates fill empty seats. White's legal moves, permission grants, ownership, timer expiry, AI moves, and restart votes all execute on the server.

First-four-moves freedom means four **human turns**. The fourth forced King takeover loses, not the third. Checkmate ends the game; stalemate pauses the board and preserves the room for voting. Other ordinary draw conditions do not end the game. Promotion decisions time out after 30 seconds to retaining Pawn ownership. Four affirmative votes restart into a lobby requiring all players to ready again.

## Realtime and persistence
Room mutations take a Mongo lease and update canonical history. Position-version checks prevent stale moves. Approval requests are tied to their board position and revalidated when approved. Mongo stores deadlines and result ledgers; process restart does not reset a clock or duplicate a result. AI calculates outside the mutation lock and checks round/position before committing. Sessions are hashed in Mongo and tokens use the pre-shipped secure storage adapter. Browser storage is not equivalent to native Keychain; consider secure HttpOnly web sessions before a standalone public web launch.

## Live voice
Voice now runs through the app's own authenticated WSS relay: **no external voice account or API key is required**. Six room members can send mono PCM16 audio at 16kHz in 80ms frames. Single-use, 60-second voice tickets are bound to a room, user, and originating revocable account session. Audio uses bounded memory-only queues and is not recorded. Clients buffer a small amount of audio to absorb jitter and drop excessive backlog rather than accumulating delay.

The browser uses Web Audio/AudioWorklet; native foreground audio runs in a persistent same-origin WebView after contextual microphone permission. Rebuild the hosted client after editing the shared transport with `node frontend/scripts/build-voice.mjs`. Voice persists while the chat sheet is closed, with mute/leave controls on the room screen. It stops when leaving the app foreground or signing out. HTTPS/WSS encrypts traffic in transit, but this is **not end-to-end encryption**. Headphones are recommended. Real-device permission, speaker/Bluetooth routing and interruption testing remain necessary.

Voice fan-out is local to one worker, with a Mongo room-owner lease preventing split rooms. The current managed runtime uses one backend worker. Multiple workers/replicas require room-sticky routing or a dedicated shared voice router. The built-in capacity is 40 simultaneous voice rooms / six participants per room, subject to actual bandwidth/CPU testing; these are safety caps, not throughput guarantees. Set `PUBLIC_APP_ORIGINS` for browser origins in addition to same-host access. The managed preview proxy can normalize the Origin header; browser Fetch Metadata and bearer-session authorization are additionally checked.

## Studio opening and account controls
The supplied CHAOS ENGINE STUDIO video is bundled and shown once per app launch, with Skip and sound controls. Native uses H.264/AAC MP4; browser uses a WebM copy of the same full footage. Nothing is cropped. Navigation back to the main menu does not replay it. WAR CHESS icon and splash assets replace template branding.

Settings includes privacy/voice information and permanent account deletion with password and DELETE confirmation. Deletion revokes sessions and voice tickets, removes submitted chat and personal ranking entries, and leaves anonymized match slots for remaining players. A durable deletion flag allows interrupted cleanup to retry automatically. Session restoration retains the saved login during transient connectivity failures, but clears expired/revoked tokens on HTTP 401.

Public `/api/health` returns minimal status; `/api/health/details` requires authentication. Public rankings omit internal account IDs. WebSockets revalidate sessions server-side and before protected state sends, independently of client heartbeats.

## Assets and licenses
- Original board/piece vectors and sound synthesis source are included. Sound files can be regenerated with `python frontend/scripts/generate_audio.py`.
- Hero artwork is hosted in managed object storage, not a data URI.
- Cinzel and Manrope fonts: SIL Open Font License; see `THIRD_PARTY_NOTICES.md`.
- Stockfish and python-chess: GPL-3.0-or-later. Stockfish runs as an external UCI process; its executable is not committed. Preserve GPL obligations when redistributing engine binaries or the python-chess-dependent backend. See third-party notices and corresponding source links.

### Managed preview launch
The protected `EXPO_PACKAGER_PROXY_URL`/`EXPO_PACKAGER_HOSTNAME` variables provide the managed reverse proxy. Do not add a second ngrok `--tunnel` to the managed supervisor command. Its configuration is marked read-only. The public frontend/backend routes have been verified using the existing proxy arrangement.

## Verification and remaining work
See `memory/PRD.md` and `test_reports/`. The application implements actual gameplay, not a visual-only prototype. Full production readiness requires load/soak testing, recovery/observability work and real-device audio verification. No native desktop executable is included.