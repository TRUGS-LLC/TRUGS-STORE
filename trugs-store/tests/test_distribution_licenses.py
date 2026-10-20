# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Check the licence files used to build wheel and source distributions."""

import tomllib
from pathlib import Path

import trugs_store


def test_distribution_license_sources():
    """Both declared licence files must equal the repository's root files."""
    package = Path(trugs_store.__file__).resolve().parents[2]
    project = tomllib.loads((package / "pyproject.toml").read_text())["project"]
    for name in ("LICENSE", "NOTICE"):
        assert (package / name).read_bytes() == (package.parent / name).read_bytes()
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE", "NOTICE"]
