"""Services package for cchooks.

This package contains business logic services including settings management,
hook validation, script generation, and template management.
"""

from .hook_validator import HookValidator

__all__ = ['HookValidator']
