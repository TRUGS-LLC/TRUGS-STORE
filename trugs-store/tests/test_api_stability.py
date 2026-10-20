# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Check public API parameters against the published trugs-store 0.1.0 wheel.

GraphStore has exactly 22 public methods. For each method and public constructor
listed in the baseline, compare every parameter's name, kind, default and
annotation in order. Optional PostgreSQL constructors are checked when available.
Public constructors also reject vocabulary opt-in parameter names.
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


def _load_baseline() -> dict[str, dict[str, list[list[str | None]]]]:
    with _FIXTURE.open() as f:
        data: dict[str, dict[str, list[list[str | None]]]] = json.load(f)
    return data


def _public_method_names(cls: type[Any]) -> list[str]:
    return sorted(
        name
        for name in dir(cls)
        if not name.startswith("_") and callable(getattr(cls, name))
    )


def _param_names(target: Any) -> list[str]:
    return list(inspect.signature(target).parameters.keys())


def _parameters(target: Any) -> list[list[str | None]]:
    """Represent ordered parameter names, kinds, defaults and annotations."""
    return [
        [
            param.name,
            param.kind.name,
            None if param.default is param.empty else repr(param.default),
            None if param.annotation is param.empty else str(param.annotation),
        ]
        for param in inspect.signature(target).parameters.values()
    ]


def test_protocol_method_count_equals_22() -> None:
    methods = _public_method_names(GraphStore)
    assert len(methods) == 22, (
        f"Expected 22 GraphStore methods; got {len(methods)}: {methods}"
    )


def test_protocol_method_parameters_match_baseline() -> None:
    baseline = _load_baseline()["GraphStore"]
    for method_name in sorted(baseline):
        member = getattr(GraphStore, method_name)
        actual = _parameters(member)
        expected = baseline[method_name]
        assert actual == expected, (
            f"GraphStore.{method_name} parameters drifted from v0.1.0: "
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
                "constructors must not require a vocabulary opt-in"
            )


def test_public_class_constructor_parameters_match_baseline() -> None:
    baseline = _load_baseline()["classes"]
    for class_name in sorted(baseline):
        if class_name not in trugs_store.__all__:
            if class_name in _CONDITIONAL_CLASSES:
                continue
            raise AssertionError(
                f"Class {class_name} was in v0.1.0 __all__ but is missing "
                "from current __all__: public-API removal is a stability "
                "break"
            )
        obj = getattr(trugs_store, class_name)
        try:
            actual = _parameters(obj.__init__)
        except (ValueError, TypeError) as exc:
            raise AssertionError(f"Cannot inspect {class_name}.__init__") from exc
        expected = baseline[class_name]
        assert actual == expected, (
            f"{class_name}.__init__ parameters drifted from v0.1.0: "
            f"baseline={expected}, current={actual}"
        )
