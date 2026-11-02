"""Opt-in smoke test that the Vue frontend really compiles.

The normal test suite stays offline and fast; this test is skipped unless
``RUN_FRONTEND_BUILD=1`` is set, because it installs Node dependencies and runs a
production build:

    RUN_FRONTEND_BUILD=1 python -m pytest tests/test_frontend_build.py -q
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DIST_INDEX = FRONTEND / "dist" / "index.html"


def _npm() -> str:
    for name in ("npm.cmd", "npm"):
        found = shutil.which(name)
        if found:
            return found
    pytest.skip("npm is not installed on this machine")


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_FRONTEND_BUILD") != "1",
    reason="set RUN_FRONTEND_BUILD=1 to install Node deps and build the Vue frontend",
)


def test_frontend_builds_with_vite():
    npm = _npm()
    subprocess.run(
        [npm, "install", "--no-audit", "--no-fund"],
        cwd=str(FRONTEND),
        check=True,
        timeout=900,
    )
    subprocess.run([npm, "run", "build"], cwd=str(FRONTEND), check=True, timeout=600)

    assert DIST_INDEX.is_file(), "vite build did not produce frontend/dist/index.html"
    bundle = DIST_INDEX.read_text(encoding="utf-8")
    assert '<div id="app">' in bundle
    # the built bundle must reference an emitted asset, proving the SFCs compiled
    assert "/assets/" in bundle
    assets = list((FRONTEND / "dist" / "assets").glob("*.js"))
    assert assets, "no JavaScript asset was emitted"
    assert any(path.stat().st_size > 1000 for path in assets), "the emitted bundle looks empty"
