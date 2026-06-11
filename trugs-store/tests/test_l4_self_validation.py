# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""L4 self-validation — the shipped TRUG validates under the v2 lexicon.

Verifies ASSERT-5 (AAA #2330): `shipped_trug SHALL VALIDATE 'via tg_validate
SUBJECT_TO v2_lexicon`. The shipped artifact is this repo's own
`folder.trug.json`; it declares `core_v2.0.0` and must validate clean under the
v2 LEVEL_PREFIX rules — **non-vacuously**, i.e. every node's `metric_level`
prefix must be one the validator actually recognizes.

The non-vacuity assertion is the regression guard for the SP4 lexicon fix: the
store's `SI_PREFIX_ORDERING` previously spelled the 10^1 prefix `"DECA"` while
the canonical v2 lexicon (and `tg validate`) use `"DEKA"`, so `prefix_of`
returned `None` for canonical nodes and the hierarchy check silently skipped
them. If that drift ever returns, `test_shipped_trug_uses_recognized_prefixes`
fails instead of passing vacuously.

Correctness-gate note (ASSERT-7): the load-bearing correctness gate for this
package is **L3 + round-trip** (`test_l3_contracts.py` + `test_round_trip.py`)
together with this L4 self-validation — *not* `mypy` alone. `mypy --strict` over
a `Dict[str, Any]` graph model is largely vacuous about graph *semantics*; it
cannot catch a hierarchy-rule or round-trip regression. The must-pass behavioral
tests are what hold the contract.

Note on `tg validate`: the TOOLS CORE-16 validator (`tg validate`) confirms the
same artifact locally under the v2 dev parser (2.0.0a1); its CI enforcement is
deferred until v2 `trugs-tools` publishes to PyPI (#1660), the same gate as the
`trug-check` job. STORE's own structural validator is the deterministic,
env-independent L4 gate exercised here.
"""

from __future__ import annotations

from pathlib import Path

from trugs_store import JsonFilePersistence
from trugs_store.validation import prefix_of
from trugs_store.vocabulary import classify_vocabulary

_FOLDER_TRUG = Path(__file__).resolve().parents[2] / "folder.trug.json"


def _load():
    return JsonFilePersistence().load(str(_FOLDER_TRUG))


def test_shipped_trug_exists() -> None:
    assert _FOLDER_TRUG.is_file(), (
        f"shipped folder.trug.json not found at {_FOLDER_TRUG}"
    )


def test_shipped_trug_declares_v2_lexicon() -> None:
    store = _load()
    assert classify_vocabulary(store.get_metadata()) == "v2", (
        "the shipped TRUG must declare core_v2.0.0 to engage v2 validation"
    )


def test_shipped_trug_uses_recognized_prefixes() -> None:
    """Non-vacuity: every shipped node's metric_level prefix is in the lexicon.

    Guards the DECA/DEKA drift class — an unrecognized prefix would make
    validation skip the node, passing vacuously.
    """
    store = _load()
    unrecognized = [
        (n["id"], n.get("metric_level"))
        for n in store.find_nodes()
        if prefix_of(n.get("metric_level")) is None
    ]
    assert not unrecognized, (
        f"shipped nodes carry metric_level prefixes the v2 lexicon does not "
        f"recognize (validation would silently skip them): {unrecognized}"
    )


def test_shipped_trug_validates_clean_under_v2() -> None:
    store = _load()
    violations = store.validate_graph()
    assert violations == [], (
        "shipped folder.trug.json must validate clean under the v2 lexicon; "
        f"got: {[(v.node_id, v.rule, v.message) for v in violations]}"
    )
