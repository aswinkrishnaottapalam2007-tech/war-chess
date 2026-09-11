# WAR CHESS readiness outcome

## Final automated status: FAIL — unresolved scanner/runtime discrepancy

User requested deployment-agent readiness health check, not actual deployment.

### Corrected and independently verified
- Managed backend/frontend environment files are available to the build context; private local overrides stay ignored.
- Explicit CORS configuration passes real authenticated preflight/GET behavior with cookies disabled.
- Stockfish no longer relies solely on manual installation in the preview image: explicit/system discovery has a pinned SHA-256-checked Linux bootstrap fallback.
- Independent testing report iteration_3: 10/10 configuration, public/private health, CORS, and auth checks passed.
- Independent testing report iteration_4: 21/21 checks passed, including real ARM64 empty-cache download, checksum checks, UCI startup and legal engine move from the downloaded executable; cached offline reuse and fail-closed integrity behavior.

### Remaining health-scan issue
The last deployment-agent scan insists that the Expo launch command needs `--tunnel`. The supervisor file is marked read-only, and the managed runtime already exposes Expo through protected `EXPO_PACKAGER_PROXY_URL`/`EXPO_PACKAGER_HOSTNAME` settings. The troubleshooting agent classified the requirement as a false positive and advised preserving the existing command. Independent tests confirmed public reachability without the flag. Repeated scan still reports FAIL, so no unconditional readiness claim is made and the supervisor was not modified.

### Separate known limits
- LiveKit credentials have not been supplied; live voice is unavailable, while text chat and chess operate independently.
- ARM64 bootstrap execution verified; AMD64 manifest pinned but hardware execution not verified here.
- First bootstrap needs access to the pinned Debian artifact and documented native libraries; custom STOCKFISH_PATH can avoid downloading.
- No actual fresh Kubernetes deployment, load certification, or native-device audio validation performed by this readiness task.