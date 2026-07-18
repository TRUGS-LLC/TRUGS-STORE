# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Vocabulary classification — TRUGS 2.0 (`core_v2.0.0`) vs the legacy path.

Per TRUGS-DEVELOPMENT AAA #1756, the package recognizes a TRUG's declared
vocabulary in `capabilities.vocabularies` and dispatches load/save through
a single coherent code path:

- declares "core_v2.0.0" → the v2 dispatch (canonical re-emit: metric-level
  stamping + a top-level ``level_directives`` field).
- otherwise              → the legacy ("v1") dispatch: plain persistence, no
  stamping. This path serves ``project_v1`` and undeclared TRUGs — the
  additive guarantee that unknown TRUGs never break. It is a persistence-
  format choice, NOT vocabulary enforcement.

Note: TRUGS CORE v1 (``core_v1.0.0``) is retired — TRUGS is v2-only. That
retirement is enforced by the CORE-16 ``trug validate`` gate in trugs-tools,
NOT here: STORE's dispatch is a structural/persistence concern deliberately
distinct from the CORE validator (see BOUNDARY.md), so a ``core_v1.0.0`` graph
is rejected upstream before it ever reaches this code. The ``"v1"`` dispatch
label is retained only as the name of the non-v2 persistence path.
"""

from __future__ import annotations

from typing import Any, Dict, Literal

# AGENT claude SHALL DEFINE RECORD V2_VOCABULARIES AS A RECORD constant.
V2_VOCABULARIES: frozenset[str] = frozenset({"core_v2.0.0"})

VocabularyDispatch = Literal["v1", "v2"]


def classify_vocabulary(trug_metadata: Dict[str, Any]) -> VocabularyDispatch:
    """Classify a TRUG's declared vocabulary as 'v2' or the legacy 'v1' path.

    Reads `metadata['capabilities']['vocabularies']` (a list of strings).
    Returns 'v2' if any declared vocabulary is in V2_VOCABULARIES; returns
    'v1' otherwise — the legacy persistence path, which also covers
    `project_v1` and the no-declaration case (additive guarantee). The 'v1'
    label denotes the non-v2 persistence path, NOT `core_v1.0.0` support
    (retired; rejected upstream by the `trug validate` CORE gate).

    <trl>
    AGENT claude SHALL DEFINE FUNCTION classify_vocabulary AS A RECORD pure_function. PROCESS classify_vocabulary SHALL READ RECORD trug_metadata THEN RETURN RECORD dispatch.
    </trl>
    """
    capabilities = trug_metadata.get("capabilities") or {}
    vocabularies = capabilities.get("vocabularies") or []
    if any(v in V2_VOCABULARIES for v in vocabularies):
        return "v2"
    return "v1"
