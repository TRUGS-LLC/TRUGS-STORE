# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Smoke checks for BOUNDARY.md — the package self-description (AAA #2330 SP3).

Automatable half of Target 3.1 (the accuracy half is a manual review logged in
the AAA Phase-10 record). Mirrors the Phase-8 audit recipes:
  PC-3: BOUNDARY.md exists + records STORE-owns / TOOLS-owns / two-validator
  SC-6: records the two-validator split *as deliberate* (not #2189 drift)
Verifies ASSERT-6 (`boundary_ownership_doc SHALL RECORD two_validator_split AS
deliberate AND SHALL_NOT FRAME 'it AS drift`) at the presence level.
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
    """ASSERT-6: the split is recorded as deliberate, distinguished from #2189."""
    text = _text().lower()
    assert "deliberate" in text or "intentional" in text, (
        "BOUNDARY.md must frame the two-validator split as deliberate/intentional"
    )
    assert "#2189" in text, (
        "BOUNDARY.md must distinguish the deliberate split from the #2189 drift"
    )


def test_readme_references_boundary_doc() -> None:
    assert "BOUNDARY.md" in _README.read_text(), (
        "README.md must link to BOUNDARY.md (package self-description)"
    )
