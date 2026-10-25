"""
Beholders security module.

This module provides security-related functionality for Beholders, including:
- Fingerprinting for component identity and tracking
- Security configuration for controlling access and permissions
- Future: authentication, scoping, and delegation mechanisms
"""

from beholders.security.fingerprint import Fingerprint
from beholders.security.security_config import SecurityConfig


__all__ = ["Fingerprint", "SecurityConfig"]
