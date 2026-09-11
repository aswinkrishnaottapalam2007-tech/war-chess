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
  voice.html         Foreground native WebView LiveKit client
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

Backend environment: see `backend/.env.example`. `MONGO_URL` is required. Optional `STOCKFISH_PATH` overrides executable discovery. Install Stockfish using your OS package manager; the checked runtime here is Debian Stockfish 15.1. Set a specific `CORS_ORIGINS` allowlist for a production environment.

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
Provide backend-only `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, then restart the backend. Credentials are never bundled into the app. Server-generated tokens restrict identity, room and publishing source to microphone. Native foreground voice runs inside an HTTPS WebView; the browser uses `livekit-client`. The vendored browser bundle is copied from the pinned SDK in `frontend/node_modules/livekit-client/dist/livekit-client.umd.js` to `backend/static/`.

**Until those credentials are supplied, live voice is unavailable and the UI says so.** Text chat is fully independent. Real-device microphone permission, audio routing, interruptions, and background behavior need verification. This initial implementation is not a substitute for production native call lifecycle testing.

## Assets and licenses
- Original board/piece vectors and sound synthesis source are included. Sound files can be regenerated with `python frontend/scripts/generate_audio.py`.
- Hero artwork is hosted in managed object storage, not a data URI.
- Cinzel and Manrope fonts: SIL Open Font License; see `THIRD_PARTY_NOTICES.md`.
- Stockfish and python-chess: GPL-3.0-or-later. Stockfish runs as an external UCI process; its executable is not committed. Preserve GPL obligations when redistributing engine binaries or the python-chess-dependent backend. See third-party notices and corresponding source links.

## Verification and remaining work
See `memory/PRD.md` and `test_reports/`. The application implements actual gameplay, not a visual-only prototype. Full production readiness requires load/soak testing, recovery/observability work and real-device audio verification. No native desktop executable is included.