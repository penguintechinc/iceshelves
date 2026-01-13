"""Authentication middleware for repo-worker service."""

import functools
import logging
from typing import Optional

from quart import Response, current_app, g, request

from app.auth.jwt import TokenPayload, decode_token, extract_token_from_header

logger = logging.getLogger(__name__)


def get_current_user() -> Optional[TokenPayload]:
    """Get the current authenticated user from request context."""
    return getattr(g, "current_user", None)


def auth_required(require_push: bool = False):
    """Decorator to require authentication.

    Args:
        require_push: If True, requires authentication even for read operations.
                     If False, allows anonymous read but requires auth for write.
    """
    def decorator(f):
        @functools.wraps(f)
        async def decorated_function(*args, **kwargs):
            config = current_app.config.get("CONFIG")
            if not config:
                return await f(*args, **kwargs)

            # Check if auth is enabled
            if not config.auth.enabled:
                return await f(*args, **kwargs)

            # Check if anonymous pull is allowed for read operations
            is_write_operation = request.method in ("POST", "PUT", "PATCH", "DELETE")
            if not is_write_operation and config.auth.anonymous_pull and not require_push:
                return await f(*args, **kwargs)

            # Extract and validate token
            auth_header = request.headers.get("Authorization", "")
            token = extract_token_from_header(auth_header)

            if not token:
                return _unauthorized_response("No valid authentication token provided")

            payload = decode_token(token, config.auth.jwt_secret_key)
            if not payload:
                return _unauthorized_response("Invalid or expired token")

            # Store user in request context
            g.current_user = payload

            return await f(*args, **kwargs)

        return decorated_function
    return decorator


def _unauthorized_response(message: str) -> Response:
    """Create an unauthorized response with WWW-Authenticate header."""
    return Response(
        message,
        status=401,
        headers={
            "WWW-Authenticate": 'Bearer realm="repo-worker",service="repo-worker"',
        },
    )


def admin_required(f):
    """Decorator to require admin role."""
    @functools.wraps(f)
    async def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return _unauthorized_response("Authentication required")

        if "admin" not in user.roles and "Admin" not in user.roles:
            return Response("Admin access required", status=403)

        return await f(*args, **kwargs)

    return auth_required(require_push=True)(decorated_function)
