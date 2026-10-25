"""Deprecated: use ``beholders_core.token_manager`` instead."""

from __future__ import annotations

import warnings

from beholders_core.token_manager import TokenManager as TokenManager


__all__ = ["TokenManager"]


warnings.warn(
    "beholders.auth.token_manager is deprecated; import from beholders_core.token_manager.",
    DeprecationWarning,
    stacklevel=2,
)
