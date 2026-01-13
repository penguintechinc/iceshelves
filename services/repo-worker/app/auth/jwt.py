"""JWT token validation for repo-worker service."""

import logging
from dataclasses import dataclass
from typing import Optional

import jwt

logger = logging.getLogger(__name__)


@dataclass
class TokenPayload:
    """Decoded JWT token payload."""
    user_id: int
    email: str
    roles: list[str]
    exp: int
    iat: int


def decode_token(token: str, secret_key: str) -> Optional[TokenPayload]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string
        secret_key: The secret key used to sign the token

    Returns:
        TokenPayload if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return TokenPayload(
            user_id=payload.get("user_id", payload.get("sub")),
            email=payload.get("email", ""),
            roles=payload.get("roles", []),
            exp=payload.get("exp", 0),
            iat=payload.get("iat", 0),
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None


def extract_token_from_header(auth_header: str) -> Optional[str]:
    """Extract token from Authorization header.

    Supports both 'Bearer <token>' and 'Basic <token>' formats.
    For Basic auth, we treat the password as the JWT token.

    Args:
        auth_header: The Authorization header value

    Returns:
        The extracted token or None
    """
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2:
        return None

    scheme, token = parts

    if scheme.lower() == "bearer":
        return token

    if scheme.lower() == "basic":
        # Decode base64 and extract password (treated as JWT)
        import base64
        try:
            decoded = base64.b64decode(token).decode("utf-8")
            if ":" in decoded:
                _, password = decoded.split(":", 1)
                return password
        except (ValueError, UnicodeDecodeError):
            pass

    return None
