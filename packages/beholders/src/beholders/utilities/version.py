"""Deprecated: use ``beholders_core.version`` instead."""

from __future__ import annotations

import warnings

from beholders_core.version import get_beholders_version as get_beholders_version


__all__ = ["get_beholders_version"]


warnings.warn(
    "beholders.utilities.version is deprecated; import from beholders_core.version.",
    DeprecationWarning,
    stacklevel=2,
)
