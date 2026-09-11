# Main-agent verification — 2026-09-11

## Initial preview
At 390×844 using the external HTTPS preview:
- Main menu painted with all three primary options.
- Settings opened; light/dark toggles updated UI.
- JOIN GAME led to email/password authentication.
- TypeScript compile and Python/JS lints passed.

## Fix verification after iteration 1
Reported mobile communications sheet overflow corrected in `src/components/ui.tsx`: numeric viewport-aware sheet height, flex-shrinking outer container, independently bounded scroll content. `DB_NAME` now fails fast if unset. Kept correct protected frontend contract `EXPO_PUBLIC_BACKEND_URL` (tester suggestion to use EXPO_BACKEND_URL was inapplicable).

Browser scenario completed successfully:
1. Sign in as king.warchess@example.com.
2. Enter existing active six-role room QXWBGQ.
3. View real board, current forced command count, and server phase.
4. Open Team chat, type and send "Hold the center. The King is listening."
5. Assert the sent message appears.
6. Switch to Voice and tap Enable microphone & join.
7. Assert clear live voice awaiting LiveKit credentials status.
8. Close sheet and interact with board.

All steps passed. Capture paths were returned by screenshot tool; some tool artifacts live outside local repo. Live microphone transport intentionally not claimed as verified.

## Final real move verification
At 390×844, signed in as King, rejoined QXWBGQ during forced command, selected g1 and f3. The server executed the authorized King takeover Nf3, Stockfish replied, and the visible strategy timer restarted at 01:00 for human turn 3. Opened Battle record and verified Nf3 persisted. All steps passed. Refined main-menu screenshot was also captured.

## Backend follow-up
Independent test agent extended core custom-rule coverage and ran 20/20 passing tests. Unit isolation uses fixture substitutes for selected database/action dependencies; production app APIs are real. Consult iteration_2.json and backend/tests for exact coverage. This is functional QA, not a load test, security audit, or device certification.