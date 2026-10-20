# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Check the licence files used to build wheel and source distributions."""

import tomllib
from pathlib import Path

# The project folder: trugs-store/ in a repository checkout, the top folder of a source distribution.
PROJECT = Path(__file__).resolve().parents[1]


def test_distribution_license_sources():
    """The project declares Apache-2.0 and its two licence files, and both files are present.

    In a repository checkout (the parent folder holds folder.trug.json), each file also equals the
    repository's root copy.
    """
    project = tomllib.loads((PROJECT / "pyproject.toml").read_text())["project"]
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE", "NOTICE"]
    repository = PROJECT.parent
    in_checkout = (repository / "folder.trug.json").is_file()
    for name in ("LICENSE", "NOTICE"):
        assert (PROJECT / name).is_file()
        if in_checkout:
            assert (PROJECT / name).read_bytes() == (repository / name).read_bytes()
