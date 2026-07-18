# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Sentinel for absent OPTIONAL third-party dependencies.

`OptionalDependencyError` is the single named discriminator between "an
optional dependency is not installed" (safe to skip — the feature stays off)
and "a module inside this package is genuinely broken" (must fail loudly).
The optional-import guards in `postgres.py` / `persistence/postgres.py` raise
it, and `__init__.py` catches ONLY it — any other ImportError propagates
(audit #2: a bare `except ImportError: pass` silently dropped the Postgres
backend on real internal breaks).
"""


class OptionalDependencyError(ImportError):
    """An optional third-party dependency is absent (feature stays disabled)."""
