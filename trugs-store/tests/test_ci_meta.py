# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""CI-contract meta-tests — guard against silent-skip of env-dependent tests.

Closes TRUGS-LLC/TRUGS-STORE-dev#16 / AAA #1756 AF-3, re-armed under
TRUGS-DEVELOPMENT AAA #2330 SP1 (ASSERT-8: `env_dependent_test SHALL RUN
positively AND SHALL_NOT silent_skip`).

The Postgres-backed tests gate on ``TRUGS_TEST_DSN`` via
``pytest.mark.skipif`` (see ``conftest.py`` / ``test_postgres_v2.py``). If the
CI ``postgres-tests`` job ever drops that env var, those tests would
skip-to-green and silently mask regressions. These structural assertions run
in the ordinary (no-DB) ``test`` job and fail the moment the CI contract
regresses — so the guard itself can never silent-skip.
"""

from pathlib import Path

import pytest

# Hard import (not importorskip): PyYAML is a declared dev dependency, so its
# absence is a misconfigured dev env — fail loudly rather than silent-skip the
# very guard whose job is to forbid silent-skips.
import yaml

# tests/ -> trugs-store/ -> repo root (where .github/ lives)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci() -> dict:
    assert _CI_YML.is_file(), f"CI workflow not found at {_CI_YML}"
    return yaml.safe_load(_CI_YML.read_text())


def _job(name: str) -> dict:
    jobs = _load_ci()["jobs"]
    assert name in jobs, f"CI job '{name}' missing — silent-skip guard cannot verify it"
    return jobs[name]


def test_postgres_job_exports_dsn() -> None:
    """The gated job must set TRUGS_TEST_DSN, or the Postgres tests silent-skip."""
    blob = yaml.safe_dump(_job("postgres-tests"))
    assert "TRUGS_TEST_DSN" in blob, (
        "postgres-tests must export TRUGS_TEST_DSN; without it the "
        "skipif-gated Postgres tests would skip-to-green (store-dev#16 / AF-3)"
    )


def test_postgres_job_runs_the_gated_files() -> None:
    """The job must invoke every TRUGS_TEST_DSN-gated test file (else it skips)."""
    blob = yaml.safe_dump(_job("postgres-tests"))
    assert "test_postgres_persistence.py" in blob
    assert "test_postgres_v2.py" in blob
    # test_round_trip.py's Postgres leg is DSN-gated too (AAA #2330 SP2).
    assert "test_round_trip.py" in blob


def test_postgres_job_has_positive_must_run_guard() -> None:
    """A step must assert the gated tests actually ran (not all-skipped)."""
    blob = yaml.safe_dump(_job("postgres-tests")).lower()
    assert "must-run" in blob or "silent-skip" in blob, (
        "postgres-tests must carry an explicit positive must-run guard step "
        "that fails if the env-dependent tests no-op"
    )


# `trug-check` is intentionally excluded: it stays a SOFT gate until the v2
# trugs-tools (CORE-16 validator + folder-governance rules) publishes to PyPI
# (TRUGS-DEVELOPMENT#1660). PyPI `trugs-tools` is still 1.0.0 (pre-v2), so a
# hard gate there cannot meaningfully validate the v2 folder.trug.json. The
# folder TRUG's v2 validity is verified locally under the dev parser and logged
# in the AAA #2330 Phase-10 record; this gate hardens when v2 ships.
@pytest.mark.parametrize("job_name", ["postgres-tests", "typecheck", "lint"])
def test_quality_gates_are_hard(job_name: str) -> None:
    """L1 + env-dependent gates must be hard (no continue-on-error: true)."""
    for step in _job(job_name).get("steps", []):
        assert not step.get("continue-on-error", False), (
            f"{job_name} step '{step.get('name', '?')}' is soft "
            f"(continue-on-error) — it cannot enforce its gate"
        )


# --- repo-hygiene guards (AAA #2330 SP1 cleanups: T1.4, T1.5) ----------------


def test_proposal_dir_absent() -> None:
    """PROPOSAL/ must not graduate to the public-bound package repo (ADR-007)."""
    assert not (_REPO_ROOT / "PROPOSAL").exists(), (
        "PROPOSAL/ planning docs must not live in a public-bound repo "
        "(ADR-007 / AAA #2330 ADR-003) — archived to TRUGS-DEVELOPMENT instead"
    )


def test_no_empty_persistence_init() -> None:
    """The empty persistence/__init__.py was removed (namespace package)."""
    assert not (
        _REPO_ROOT
        / "trugs-store"
        / "src"
        / "trugs_store"
        / "persistence"
        / "__init__.py"
    ).exists()
