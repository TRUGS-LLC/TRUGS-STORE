# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Regression-guard tests for trugs-store public API stability vs the v0.1.0 baseline.

Pins the 4 ASSERTions of AAA #1756 §"API-surface stability"
(TRUGS-LLC/TRUGS-STORE-dev#9):

1. GraphStore protocol has exactly 22 public methods
2. Each protocol method's signature is byte-equivalent to v0.1.0
3. No public class constructor takes a v2-dispatch opt-in kwarg
4. Each public class constructor's signature is byte-equivalent to v0.1.0

Baseline source: commit 844f5f8 ("chore(import): vendor trugs-store v0.1.0 baseline").
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any

import trugs_store
from trugs_store.protocol import GraphStore

_FIXTURE = Path(__file__).parent / "fixtures" / "api_signatures_v0_1_0.json"

_V2_KWARG_PATTERN = re.compile(r"v2|vocabulary|core_v2|enable_v2|use_v2")

# Classes present in __all__ only when the optional `postgres` extra is installed.
# CI's postgres-tests job has psycopg installed; other matrix jobs do not.
_CONDITIONAL_CLASSES = frozenset({"PostgresGraphStore", "PostgresPersistence"})


def _load_baseline() -> dict[str, dict[str, list[str]]]:
    with _FIXTURE.open() as f:
        data: dict[str, dict[str, list[str]]] = json.load(f)
    return data


def _public_method_names(cls: type[Any]) -> list[str]:
    return sorted(
        name
        for name in dir(cls)
        if not name.startswith("_") and callable(getattr(cls, name))
    )


def _param_names(target: Any) -> list[str]:
    return list(inspect.signature(target).parameters.keys())


def test_protocol_method_count_equals_22() -> None:
    methods = _public_method_names(GraphStore)
    assert len(methods) == 22, (
        f"Expected 22 GraphStore methods; got {len(methods)}: {methods}"
    )


def test_protocol_method_signatures_byte_equivalent_to_baseline() -> None:
    baseline = _load_baseline()["GraphStore"]
    for method_name in sorted(baseline):
        member = getattr(GraphStore, method_name)
        actual = _param_names(member)
        expected = baseline[method_name]
        assert actual == expected, (
            f"GraphStore.{method_name} signature drifted from v0.1.0: "
            f"baseline={expected}, current={actual}"
        )


def test_no_v2_kwarg_in_any_public_constructor() -> None:
    for class_name in sorted(trugs_store.__all__):
        obj = getattr(trugs_store, class_name)
        if not inspect.isclass(obj):
            continue
        try:
            params = _param_names(obj.__init__)
        except (ValueError, TypeError):
            continue
        for param in params:
            assert _V2_KWARG_PATTERN.search(param) is None, (
                f"{class_name}.__init__ exposes v2-dispatch kwarg '{param}': "
                "constructors are byte-stable per AAA #1756 §API-surface stability"
            )


def test_public_class_constructor_signatures_byte_equivalent_to_baseline() -> None:
    baseline = _load_baseline()["classes"]
    for class_name in sorted(baseline):
        if class_name not in trugs_store.__all__:
            if class_name in _CONDITIONAL_CLASSES:
                continue
            raise AssertionError(
                f"Class {class_name} was in v0.1.0 __all__ but is missing "
                "from current __all__: public-API removal is a stability "
                "break per AAA #1756 §API-surface stability"
            )
        obj = getattr(trugs_store, class_name)
        try:
            actual = _param_names(obj.__init__)
        except (ValueError, TypeError):
            continue
        expected = baseline[class_name]
        assert actual == expected, (
            f"{class_name}.__init__ signature drifted from v0.1.0: "
            f"baseline={expected}, current={actual}"
        )
