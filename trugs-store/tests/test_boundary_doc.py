# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Smoke checks for BOUNDARY.md — the package self-description.

Presence checks for BOUNDARY.md: it records STORE-owns / TOOLS-owns and
the two-validator split as deliberate, rather than drift. These tests check
that the ownership document exists and states the distinction; accuracy
also requires review against the implementations.
"""

from __future__ import annotations

from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[1]
_BOUNDARY = _PKG_ROOT / "BOUNDARY.md"
_README = _PKG_ROOT / "README.md"


def _text() -> str:
    assert _BOUNDARY.is_file(), "BOUNDARY.md missing from the package root"
    return _BOUNDARY.read_text()


def test_boundary_doc_records_ownership() -> None:
    text = _text().lower()
    assert "store owns" in text, "BOUNDARY.md must record what STORE owns"
    assert "tools owns" in text, "BOUNDARY.md must record what TOOLS owns"


def test_boundary_doc_records_two_validator_split() -> None:
    text = _text().lower()
    assert "two-validator" in text or "two validator" in text, (
        "BOUNDARY.md must record the two-validator split"
    )


def test_two_validator_split_framed_as_deliberate_not_drift() -> None:
    """The split is recorded as deliberate, distinguished from drift."""
    text = _text().lower()
    assert "deliberate" in text or "intentional" in text, (
        "BOUNDARY.md must frame the two-validator split as deliberate/intentional"
    )
    assert "not drift" in text, (
        "BOUNDARY.md must describe the deliberate split as not drift"
    )


def test_readme_references_boundary_doc() -> None:
    assert "BOUNDARY.md" in _README.read_text(), (
        "README.md must link to BOUNDARY.md (package self-description)"
    )
