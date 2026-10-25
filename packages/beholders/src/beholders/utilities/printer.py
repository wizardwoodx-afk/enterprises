"""Deprecated: use ``beholders_core.printer`` instead."""

from __future__ import annotations

import warnings

from beholders_core.printer import (
    PRINTER as PRINTER,
    ColoredText as ColoredText,
    Printer as Printer,
    PrinterColor as PrinterColor,
)


__all__ = ["PRINTER", "ColoredText", "Printer", "PrinterColor"]


warnings.warn(
    "beholders.utilities.printer is deprecated; import from beholders_core.printer.",
    DeprecationWarning,
    stacklevel=2,
)
