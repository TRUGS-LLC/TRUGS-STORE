# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""L3 contract scanner — every concrete public surface carries a <trl> block.

Verifies ASSERT-3 (AAA #2330): `EACH public_function 'in store_pkg SHALL CARRY
RECORD trl_contract`, where a contract is a ``<trl>…</trl>`` block in the
object's docstring (the convention used across trugs-tools).

Scope: public classes + public functions/methods (name not ``_``-prefixed) in
``src/trugs_store``. **Stub-bodied functions are excluded** — a function whose
body is only ``...``/``pass`` (e.g. a ``GraphStore`` Protocol method) is an
interface declaration with no behavior; its behavioral contract lives on the
concrete implementation (``InMemoryGraphStore`` / ``PostgresGraphStore``), and
the interface's identity contract lives on the Protocol *class* docstring.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_PKG = Path(__file__).resolve().parents[1] / "src" / "trugs_store"


def _is_stub(node: ast.AST) -> bool:
    """Body is only a docstring and/or ``...``/``pass`` — no behavior."""
    for stmt in node.body:  # type: ignore[attr-defined]
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            if stmt.value.value is Ellipsis or isinstance(stmt.value.value, str):
                continue
        if isinstance(stmt, ast.Pass):
            continue
        return False
    return True


def _targets():
    """Yield (module_relpath, qualname, docstring) for every contract target."""
    for path in sorted(_PKG.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        rel = path.relative_to(_PKG.parent.parent).as_posix()
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_") and not _is_stub(node):
                    yield rel, node.name, ast.get_docstring(node)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                yield rel, node.name, ast.get_docstring(node)
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not sub.name.startswith("_") and not _is_stub(sub):
                            yield rel, f"{node.name}.{sub.name}", ast.get_docstring(sub)


_TARGETS = list(_targets())


def test_targets_discovered() -> None:
    """Guard against a silently-empty scan (e.g. a moved package root)."""
    assert len(_TARGETS) >= 60, (
        f"expected the full public surface, found {len(_TARGETS)}"
    )


@pytest.mark.parametrize(
    "qualname,docstring",
    [(f"{rel}::{q}", doc) for rel, q, doc in _TARGETS],
    ids=[f"{rel}::{q}" for rel, q, _ in _TARGETS],
)
def test_public_surface_carries_trl_contract(
    qualname: str, docstring: str | None
) -> None:
    assert docstring is not None, (
        f"{qualname} has no docstring (needs a <trl> contract)"
    )
    assert "<trl>" in docstring and "</trl>" in docstring, (
        f"{qualname} docstring carries no <trl>…</trl> contract block"
    )
    body = docstring.split("<trl>", 1)[1].split("</trl>", 1)[0].strip()
    assert body, f"{qualname} has an empty <trl> block"
