"""pytest fixtures + auto-regeneration shim for Sprint 5/E2 self-test.

The 19 tests in `test_verify_action.py` read `tests/fixtures/manifest.json` at
module-import time (collection phase). On a fresh clone, manifest.json + the 3
envelope fixtures + test-keys don't yet exist — the import fails with
FileNotFoundError before any test runs. This module installs a
session-scoped, autouse fixture that runs `tests/fixtures/generate_fixtures.py`
exactly once per session IF manifest.json is missing, so pytest collection
works on fresh checkouts.

/quality-gate Phase 2 cycle 1 remediation of Lane B Agent 1 F2.

Re-runs are skipped when manifest.json exists, so this adds no cost to the
hot path; only fresh checkouts (or post-`git clean -fdx`) pay the ~3-5s
keypair-generation cost.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
GENERATOR = FIXTURES_DIR / "generate_fixtures.py"
MANIFEST = FIXTURES_DIR / "manifest.json"


@pytest.fixture(scope="session", autouse=True)
def _ensure_fixtures_generated() -> None:
    """Run `generate_fixtures.py` once per test session if manifest.json is missing.

    Fail-loud (raise) if the generator script itself errors, so a broken
    generator doesn't leave the test suite passing against stale fixtures.
    """
    if MANIFEST.exists():
        return
    if not GENERATOR.exists():
        pytest.fail(
            f"manifest.json missing AND {GENERATOR} missing — "
            "cannot bootstrap Sprint 5/E2 self-test fixtures"
        )
    result = subprocess.run(
        [sys.executable, str(GENERATOR)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        # Documented at 3-5s. Bound it anyway: this is session-scoped autouse,
        # so a hang here stalls collection itself with no test output to explain
        # why. stdin=DEVNULL so it can never block waiting on input.
        timeout=120,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        pytest.fail(
            f"generate_fixtures.py exited {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    if not MANIFEST.exists():
        pytest.fail(
            f"generate_fixtures.py exited 0 but {MANIFEST} still missing"
        )
