"""Iteration 6 manual-playwright record: cross-site websocket probe.

From https://example.com, attempted websocket to:
- wss://six-role-battle.preview.emergentagent.com/api/ws/ABCDEF

Observed outcome:
- websocket closed with code 1008 (opened then denied)
Used to validate public cross-site boundary behavior (Sec-Fetch-Site path).
"""
