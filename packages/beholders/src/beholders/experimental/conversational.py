"""Deprecated compatibility alias for :mod:`beholders.flow.conversational`."""

import sys

from beholders.flow import conversational as _real


sys.modules[__name__] = _real
