# WAR CHESS

## Problem statement
Build a premium cooperative chess strategy game: exactly six human roles (King, Queen, Rook, Bishop, Knight, Pawn) share White against real Stockfish. Authoritative backend handles accounts, role locks, approvals, a 60-second team clock, forced King control, elimination, promotion revival, restarting, rankings, and synchronized communications. Native mobile first, adaptive desktop browser preview. Black/gold dark theme and white/light-blue light theme.

## Explicit user choices
- Four **human-team turns** constitute opening freedom.
- Email/password accounts.
- Live voice plus text; players choose, voice recommended. User intends to provide LiveKit credentials but has not supplied values.
- Stalemate leaves room active with four-vote restart; draws are non-terminal.
- iOS/Android priority with desktop-friendly preview.
- One player chooses one locked role; all six roles must fill. Original ready requirement retained: all six ready before auto-start.

## Architecture
- Expo 57 / React Native 0.86 / Expo Router / TypeScript; existing package versions preserved.
- FastAPI, Motor/MongoDB, Argon2 passwords, hashed opaque 30-day revocable sessions.
- Mongo-backed per-room mutation leases, canonical move history, position version checks, persisted server deadlines and results.
- WebSockets with authenticated handshake, heartbeat revalidation, reconnection and 5-second HTTP fallback.
- python-chess for complete legal move validation, bounded Stockfish UCI subprocess jobs at four genuinely different search/skill limits.
- Native LiveKit voice via HTTPS WebView bridge; web via LiveKit SDK. Tokens scoped by authenticated room membership, microphone-only publishing.
- Global theme tokens only in frontend/src/theme.ts; original vector piece artwork, managed-storage hero image, original generated sound samples, expo-speech announcements.

## Personas
1. Commander: chooses one role, cooperates and makes permitted moves.
2. King: approves restricted actions and handles up to three forced takeovers.
3. Eliminated spectator: follows battle, votes, chats, and can return through promotion.

## Static core requirements
- Exactly six roles, no role switching during a match; no match before six ready players.
- Pawn always free; Queen captures need approval; R/B/N opening freedom then restricted, lone survivor moves freely but captures require approval.
- One minute each human turn; fourth forced King takeover causes team defeat.
- Normal chess legality (including castling, en passant, check, checkmate, promotion); standard draws non-terminal.
- Promoted pieces owned by Pawn unless transferred to an eligible spectating eliminated role; players who left cannot revive.
- Four yes votes reset into a ready-up lobby; role leaderboards use completed results only.
- Exactly three primary main menu options, whole-app themes, volume controls, smooth movement, selective knight jump.

## Implemented — 2026-09-11
- Full account sign-up/sign-in/session/logout and error/loading states.
- Room creation, browse/join code, share/copy, six-role selection/locking, ready auto-start, difficulty selection.
- Server authoritative gameplay, AI, approvals, timers, forced King loss, elimination, spectating, promotion ownership, voting, durable results/rankings.
- Functional touch board, permission cues, command panels, event log, move record, chat, result screens.
- Text chat, LiveKit room/token and client plumbing; voice configuration gate is explicit while keys are absent.
- Premium menu, guide, settings, leaderboards, native safe areas and keyboard support; adaptive desktop layout.
- TypeScript compile and backend/frontend lint passed. Mobile preview verified home, global theme switch, and auth navigation.
- Independent QA: 20/20 backend tests passed (real API/Stockfish integration plus isolated custom-rule unit tests). Reports: test_reports/iteration_1.json and iteration_2.json.
- Fixed mobile bottom-sheet viewport bug using bounded height + independent scroll area. Self-verification passed live match rendering, real text message send/persistence, voice-tab tap, and explicit missing-LiveKit configuration feedback at 390x844.
- Desktop adaptive layouts verified by testing agent. No production implementation changes made by testing agents.
- Final live UI test executed King takeover Nf3, received a real Stockfish reply, verified the new 01:00 strategy clock and persisted move record. All successful.

## Prioritized backlog / next tasks
### P0
- Supply LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET and verify actual six-device audio. No real voice credentials currently exist.
### P1
- Physical iOS/Android voice permission/routing/background and interruption verification; WebView voice is foreground-focused and is not native call audio.
- Load/soak tests, operational monitoring, reconnect and database failure testing before claiming production readiness.
- Password recovery/email verification (not part of current auth flow).
### P2
- In-app invitation links and richer ranking statistics.
- Modular custom board textures/skins, further 3D-quality polish and professionally recorded wood samples.
- Lobby abandonment recovery policy without weakening role locks.

## Known scope boundaries
No native Windows/macOS executable. Desktop is an adaptive browser preview. No guarantee of production readiness from initial implementation. Voice credentials and real-device testing remain necessary.

## Deployment-readiness follow-up
- User requested deployment-agent health check, with mandatory independent testing of any fixes.
- Initial readiness scan flagged root .gitignore excluding managed environment configuration and missing explicit backend CORS_ORIGINS.
- Removed blanket environment-file exclusions while retaining private .env*.local exclusions; added explicit CORS_ORIGINS="*" without changing protected connection values. Bearer authentication still uses allow_credentials=False.
- Independent testing agent verified both fixes: **10/10 focused checks passed**, including gitignore behavior, preserved protected values, clean backend restart, internal/external Mongo/Stockfish health, actual OPTIONS/GET CORS headers, and authenticated public-URL login/profile/rooms.
- Report: /app/test_reports/iteration_3.json; regression suite: backend/tests/test_deployment_readiness_config.py.
- Final deployment-agent rescan requested after independent verification. No deployment has been performed by this task.
- LiveKit credentials and live audio remain unavailable; production load/device validation remains separate from this configuration-readiness check.
- A subsequent scan incorrectly required --tunnel. Read-only troubleshooting confirmed the managed EXPO_PACKAGER_PROXY_URL reverse proxy is the supported working setup; supervisor is explicitly read-only and remains unchanged. Static managed hero artwork is an intentional asset URL, not a hardcoded API endpoint.
- Troubleshooting identified that manually installed Stockfish alone would not guarantee a fresh image. Added a standard-library, checksum-pinned Debian engine bootstrap (Linux arm64/amd64), preserving explicit/system engine preference and requiring a valid UCI handshake before caching. No root installation is needed. Fresh-cache runtime testing requested independently.
- Independent iteration_4 verification passed **21/21 checks**: real empty-cache ARM64 download, both integrity checks, executable UCI handshake and legal engine move from the downloaded binary, offline cache reuse, corruption failure, path precedence, prior config/rules regressions, and public preview reachability without --tunnel. Report: test_reports/iteration_4.json.
- AMD64 artifact is pinned but runtime execution was not tested on this ARM64 host; a fresh Kubernetes deployment was not performed. The cold-cache path was verified in the current compatible Debian runtime. First-use download connectivity/native-library requirements are documented in README.
- **Final readiness scan remains FAIL**, solely because deployment_agent insists on --tunnel in the explicitly read-only managed supervisor file. This conflicts with the troubleshoot_agent conclusion and independent tests showing the protected reverse proxy works without it. No supervisor changes were made to satisfy the scanner at the expense of the supported runtime. Compilation, environment, CORS, build-context, database, and app URL checks all passed in the final scan.
- Outstanding readiness action: resolve the scanner's managed-proxy/supervisor check discrepancy. Do not claim unconditional deployment readiness while the automated scan is still failing. No deployment was performed.

## Read-only security audit follow-up
- User requested a deployed-app audit, supplied no live URL, and authorized proceeding with best judgment. Security audit agent reviewed current code/config; production runtime identity/TLS/headers/edge and LiveKit provider settings were not confirmed.
- Verdict: conditional pass, medium confidence; no Critical/High vulnerabilities identified in reviewed source, not an unconditional production security sign-off.
- SEC-001 LOW/likely: existing WebSocket broadcasts may continue after logout/session revocation if the client withholds heartbeat; server-side revocation/expiry enforcement recommended.
- SEC-002 LOW/confirmed in source: public role leaderboard returns internal user UUIDs alongside names/statistics; remove internal identifiers or restrict intended visibility.
- Hardening: per-user connection/resource limits, minimal public health metadata, appropriate browser origin restrictions, production security headers/TLS verification.
- Report saved at test_reports/security_audit.md. No application or infrastructure fixes were applied during this read-only audit. Subsequent fixes require independent testing-agent verification before being marked resolved.