"""Bound multipart bytes before Starlette spools an untrusted upload to disk."""

import re
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from .extraction import MAX_BYTES


class KnowledgeUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not re.fullmatch(r"/api/v1/lodges/[^/]+/ai/knowledge", scope["path"])
        ):
            return await self.app(scope, receive, send)
        maximum = MAX_BYTES + 65536
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = maximum + 1
        if length > maximum:
            return await JSONResponse(
                {"detail": "Choose a file up to 10 MB"}, status_code=413
            )(scope, receive, send)
        total = 0

        async def limited():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > maximum:
                raise HTTPException(413, "Choose a file up to 10 MB")
            return message

        return await self.app(scope, limited, send)
