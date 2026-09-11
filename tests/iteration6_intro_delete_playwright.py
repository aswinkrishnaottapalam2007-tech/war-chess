"""Iteration 6 manual-playwright record: studio intro + delete-account checks.

Executed via mcp_browser_automation against:
- https://six-role-battle.preview.emergentagent.com

Key observed checks:
1) Studio intro visible with logo
2) HTML video currentTime advanced over time (playback active)
3) Skip-intro from playing state transitions to home menu
4) Cold reload immediate-skip path and natural-completion path validated
5) No intro replay during in-app navigation (home -> settings -> home)
6) Delete-account modal controls tappable (open/cancel/confirm)
7) Post-delete credential denial confirmed via API login 401
"""
