from __future__ import annotations

import json
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _int_env(name: str, default: int, *, minimum: int = 1, maximum: int = 100000) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _query_depth(query: str) -> int:
    depth = 0
    maximum = 0
    in_string = False
    escape = False
    for char in query:
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
            maximum = max(maximum, depth)
        elif char == "}":
            depth = max(0, depth - 1)
    return maximum


class GraphQLLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path != "/graphql" or request.method.upper() != "POST" or not _bool_env("EOX_GRAPHQL_LIMITS_ENABLED", True):
            return await call_next(request)
        body = await request.body()
        max_chars = _int_env("EOX_GRAPHQL_MAX_QUERY_CHARS", 20000, maximum=500000)
        max_depth = _int_env("EOX_GRAPHQL_MAX_DEPTH", 10, maximum=100)
        if len(body) > max_chars:
            return JSONResponse({"detail": "GraphQL query is too large", "max_query_chars": max_chars}, status_code=413)
        query = ""
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
            query = str(payload.get("query") or "")
        except Exception:
            query = body.decode("utf-8", errors="ignore")
        depth = _query_depth(query)
        if depth > max_depth:
            return JSONResponse({"detail": "GraphQL query depth limit exceeded", "depth": depth, "max_depth": max_depth}, status_code=400)
        request._body = body  # let Strawberry read the body after this middleware
        return await call_next(request)
