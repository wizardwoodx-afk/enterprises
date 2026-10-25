"""Deprecated: use ``beholders_core.lock_store`` instead."""

from __future__ import annotations

import warnings

from beholders_core.lock_store import lock as lock


__all__ = ["lock"]


warnings.warn(
    "beholders.utilities.lock_store is deprecated; import from beholders_core.lock_store.",
    DeprecationWarning,
    stacklevel=2,
)
