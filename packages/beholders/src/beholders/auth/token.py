"""Re-exports of authentication token helpers from ``beholders_core.auth.token``."""

from __future__ import annotations

from beholders_core.auth.token import (
    AuthError as AuthError,
    get_auth_token as get_auth_token,
)


__all__ = ["AuthError", "get_auth_token"]
