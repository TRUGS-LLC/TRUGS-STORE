# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Vocabulary classification — TRUGS 2.0 (`core_v2.0.0`) vs legacy v1.

Per TRUGS-DEVELOPMENT AAA #1756, the package recognizes a TRUG's declared
vocabulary in `capabilities.vocabularies` and dispatches load/save through
a single coherent code path:

- v2 TRUG    — declares "core_v2.0.0"          → v2 dispatch path
- v1 TRUG    — declares "core_v1.0.0" or "project_v1" → v1 dispatch path
- no decl    — defaults to v1 (additive guarantee — never break unknown TRUGs)
"""

from __future__ import annotations

from typing import Any, Dict, Literal

# AGENT claude SHALL DEFINE RECORD V1_VOCABULARIES AS A RECORD constant.
V1_VOCABULARIES: frozenset[str] = frozenset({"core_v1.0.0", "project_v1"})

# AGENT claude SHALL DEFINE RECORD V2_VOCABULARIES AS A RECORD constant.
V2_VOCABULARIES: frozenset[str] = frozenset({"core_v2.0.0"})

VocabularyDispatch = Literal["v1", "v2"]


def classify_vocabulary(trug_metadata: Dict[str, Any]) -> VocabularyDispatch:
    """Classify a TRUG's declared vocabulary as 'v1' or 'v2'.

    Reads `metadata['capabilities']['vocabularies']` (a list of strings).
    Returns 'v2' if any declared vocabulary is in V2_VOCABULARIES.
    Returns 'v1' otherwise (including the no-declaration case — additive
    guarantee: an unknown TRUG defaults to the legacy validation path).

    <trl>
    AGENT claude SHALL DEFINE FUNCTION classify_vocabulary AS A RECORD pure_function. PROCESS classify_vocabulary SHALL READ RECORD trug_metadata THEN RETURN RECORD dispatch.
    </trl>
    """
    capabilities = trug_metadata.get("capabilities") or {}
    vocabularies = capabilities.get("vocabularies") or []
    if any(v in V2_VOCABULARIES for v in vocabularies):
        return "v2"
    return "v1"
