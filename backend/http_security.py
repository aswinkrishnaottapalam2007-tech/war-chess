from starlette.responses import JSONResponse


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            too_large = int(headers.get(b'content-length', b'0')) > 16384
        except ValueError:
            too_large = True
        if too_large:
            return await JSONResponse({'detail': 'Request body exceeds the allowed size.'}, status_code=413)(scope, receive, send)

        async def secured_send(message):
            if message['type'] == 'http.response.start':
                policy = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
                if scope['path'] == '/api/voice-client':
                    policy = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' wss:; media-src 'self' blob:; worker-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
                message['headers'] = list(message.get('headers', [])) + [
                    (b'x-content-type-options', b'nosniff'), (b'x-frame-options', b'DENY'),
                    (b'referrer-policy', b'no-referrer'),
                    (b'permissions-policy', b'camera=(), microphone=(self), geolocation=()'),
                    (b'strict-transport-security', b'max-age=31536000; includeSubDomains'),
                    (b'content-security-policy', policy.encode()),
                ]
                if not scope['path'].startswith('/api/static/'):
                    message['headers'].append((b'cache-control', b'no-store'))
            await send(message)
        await self.app(scope, receive, secured_send)