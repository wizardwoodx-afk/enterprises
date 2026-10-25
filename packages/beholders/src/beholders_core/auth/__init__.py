"""OAuth2 authentication primitives — shared by beholders and beholders-cli."""

from __future__ import annotations

from beholders_core.auth.oauth2 import (
    AuthenticationCommand as AuthenticationCommand,
    Oauth2Settings as Oauth2Settings,
    ProviderFactory as ProviderFactory,
)
from beholders_core.auth.token import (
    AuthError as AuthError,
    get_auth_token as get_auth_token,
)
from beholders_core.auth.utils import validate_jwt_token as validate_jwt_token


__all__ = [
    "AuthError",
    "AuthenticationCommand",
    "Oauth2Settings",
    "ProviderFactory",
    "get_auth_token",
    "validate_jwt_token",
]
