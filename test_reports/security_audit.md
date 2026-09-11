# WAR CHESS security audit

## Outcome
**CONDITIONAL PASS — NEEDS ATTENTION. Confidence: medium.**

No Critical or High vulnerabilities were identified by the read-only security auditor in the reviewed source/configuration. This is not proof that the application is vulnerability-free or a production security sign-off.

The user requested the deployed app but did not provide a production URL, then authorized proceeding with best judgment. The configured endpoint was identifiable as a preview, not a confirmed production target. This audit reviewed source and configuration; the auditor did not authenticate, modify application data, or perform network exploitation. Production TLS, response headers, reverse-proxy enforcement, and LiveKit provider settings remain unverified.

## SEC-001 — LOW — Likely: WebSocket updates can continue after session revocation

**Evidence:** `backend/server.py:152–159` revalidates the session on a client-sent ping, while `backend/game_service.py:59–66` broadcasts state to open sockets without checking whether their sessions remain valid.

**Scenario:** A legitimately connected room member logs out or has their session revoked, but keeps the socket open and withholds heartbeats. Server-initiated match updates, including room chat in the state payload, may continue reaching that socket.

**Impact:** Continued access to a previously joined room after revocation. This does not by itself demonstrate unauthorized access to other rooms or permission to perform actions after logout. Runtime reproduction was not performed in this read-only audit.

**Recommendation:** Associate connections with session identity and expiry, and close them on revocation or server-side revalidation. Do not rely on an untrusted client to initiate the check. Cover both broadcasts and expiry without client heartbeats.

**Required verification after a fix:** Open a socket, revoke its session, send no ping, trigger a room update, and verify that no further protected state is delivered and the connection closes.

References: CWE-613; OWASP authentication/session-management controls.

## SEC-002 — LOW — Confirmed in source: Public leaderboard exposes internal user IDs

**Evidence:** `backend/server.py:103–111` serves `/api/leaderboards/{role}` without authentication and includes `user_id`, display name, and statistics in the response projection.

**Impact:** Anonymous callers can obtain internal UUIDs and associate names with statistics. A UUID is not an authentication credential, so this finding does not establish account takeover. Public display names/statistics may be intentional; internal identifiers are unnecessary disclosure unless explicitly required.

**Recommendation:** Remove internal IDs from public responses or use an intentionally public ranking identifier. Require authentication if leaderboard visibility is meant to be limited to players.

**Required verification after a fix:** Request each role leaderboard without authentication and verify that internal account identifiers are absent, while intended public ranking functionality remains intact.

References: CWE-213; OWASP API3 property-level data exposure.

## Additional hardening recommendations
- Add per-user and global WebSocket connection/action limits to reduce authenticated resource-exhaustion risk. The engine semaphore bounds concurrent calculations but is not a complete abuse-control system.
- Consider narrower browser CORS origins where appropriate. Current wildcard CORS uses `allow_credentials=False` and bearer tokens, so it is not inherently a credentialed-cookie CSRF vulnerability.
- Reduce public `/api/health` metadata to necessary health information; keep detailed engine/voice configuration diagnostics restricted if not needed publicly.
- Verify HTTPS enforcement, certificate configuration, HSTS, CSP, frame restrictions, and reverse-proxy behavior against the actual production endpoint.
- Verify live voice room admission/revocation and provider controls once LiveKit credentials exist. Real voice transport was not tested.

## Positive controls observed
- Server-side ownership, move legality, approval, turn/version, promotion, and restart validation.
- Argon2 password hashing and random opaque sessions stored as hashes with expiration.
- Parameterized Mongo operations; no reachable user-controlled query-operator or shell-command injection sink identified during source inspection.
- React Native text rendering and voice-client `textContent` use rather than direct chat HTML injection.
- Pinned engine package/executable checksums, HTTPS artifact download, exact executable extraction, and list-argument subprocess execution.
- No committed secret values identified by the auditor in the inspected tracked files. This observation does not replace continuous secret scanning.

## Changes and follow-up
No application code, credentials, account data, room data, or infrastructure was changed for this audit. Only this report and the project audit notes were saved. Recommended security fixes have **not** been applied or verified. Any subsequent fix must be independently tested by the testing agent before it is reported resolved, as the user requested.