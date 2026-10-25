"""Deprecated compatibility alias for :mod:`beholders.flow.conversational_mixin`."""

import sys

from beholders.flow import conversational_mixin as _real


sys.modules[__name__] = _real
