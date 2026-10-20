# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""CI-contract meta-tests — guard against silent-skip of env-dependent tests.

Checks that workflow-dependent tests run positively instead of silently
skipping when a workflow is supplied. This repository has no CI workflow;
the workflow-dependent checks skip until one is present.

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


# Per-function gate: only the CI-contract guards below depend on
# a published .github/workflows/ci.yml, which is not shipped in this
# public repo. Gate EXACTLY those guards (never module-level) so the always-on repo-hygiene guards
# (test_proposal_dir_absent, test_no_empty_persistence_init) keep running. They re-arm the moment a
# real ci.yml lands.
_ci_required = pytest.mark.skipif(
    not _CI_YML.is_file(),
    reason=(
        "ci.yml not published in this repo yet; "
        "the 6 CI-contract guards re-arm automatically when it lands"
    ),
)


@_ci_required
def test_postgres_job_exports_dsn() -> None:
    """The gated job must set TRUGS_TEST_DSN, or the Postgres tests silent-skip."""
    blob = yaml.safe_dump(_job("postgres-tests"))
    assert "TRUGS_TEST_DSN" in blob, (
        "postgres-tests must export TRUGS_TEST_DSN; without it the "
        "skipif-gated Postgres tests would skip-to-green"
    )


@_ci_required
def test_postgres_job_runs_the_gated_files() -> None:
    """The job must invoke every TRUGS_TEST_DSN-gated test file (else it skips)."""
    blob = yaml.safe_dump(_job("postgres-tests"))
    assert "test_postgres_persistence.py" in blob
    assert "test_postgres_v2.py" in blob
    # test_round_trip.py's Postgres leg is DSN-gated too.
    assert "test_round_trip.py" in blob


@_ci_required
def test_postgres_job_has_positive_must_run_guard() -> None:
    """A step must assert the gated tests actually ran (not all-skipped)."""
    blob = yaml.safe_dump(_job("postgres-tests")).lower()
    assert "must-run" in blob or "silent-skip" in blob, (
        "postgres-tests must carry an explicit positive must-run guard step "
        "that fails if the env-dependent tests no-op"
    )


# `trug-check` is excluded from the hard-gate assertions below.
# trugs-tools 2.4.0 supplies the v2 CORE-16 validator; the shipped folder
# graph can be checked directly with `trug validate folder.trug.json`.
# This repository has no CI workflow, so no `trug-check` job runs here.
@_ci_required
@pytest.mark.parametrize("job_name", ["postgres-tests", "typecheck", "lint"])
def test_quality_gates_are_hard(job_name: str) -> None:
    """Env-dependent and quality gates must be hard (no continue-on-error: true)."""
    for step in _job(job_name).get("steps", []):
        assert not step.get("continue-on-error", False), (
            f"{job_name} step '{step.get('name', '?')}' is soft "
            f"(continue-on-error) — it cannot enforce its gate"
        )


# --- repo-hygiene guards -------------------------------------------------------


def test_proposal_dir_absent() -> None:
    """PROPOSAL/ must not graduate to the public-bound package repo."""
    assert not (_REPO_ROOT / "PROPOSAL").exists(), (
        "PROPOSAL/ planning docs must not live in a public-bound repo; "
        "archive them outside this repository instead"
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
