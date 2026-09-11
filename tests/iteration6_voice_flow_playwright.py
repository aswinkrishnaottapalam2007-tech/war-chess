"""Iteration 6 manual-playwright record: two-page web voice flow.

Executed via mcp_browser_automation against:
- https://six-role-battle.preview.emergentagent.com

Key verified steps:
1) Create isolated accounts via real /api/auth/register + /api/auth/login
2) Create room, join second user, assign king/queen via /api endpoints
3) Login both users in separate browser contexts (mobile viewport 390x844)
4) Open room -> Team communications -> voice tab
5) Join voice on both users
6) Verify participant roster + receiving-audio indicator
7) Mute/unmute, leave from user2, roster updates on user1
8) Close sheet, confirm active voice bar remains visible
9) Leave via active voice bar
10) Cleanup temp accounts via /api/auth/delete-account
"""
