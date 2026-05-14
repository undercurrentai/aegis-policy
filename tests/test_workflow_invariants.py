"""Static-validation tests for the Sprint 5/E3 workflow files.

These tests guard against /quality-gate Phase 2 bug-hunt findings (F1+F2+F4)
recurring silently. They parse the YAML statically rather than running the
workflows (which requires GitHub Actions + AEGIS_SDK_FETCH_TOKEN).

Findings caught:

F1+F2 (HIGH/C3): aegis-verify-attestation.yml's inner actions/checkout step
must use `github.workflow_sha` as the ref — NOT `github.event.workflow.ref`
(which is not a documented GitHub Actions context variable for workflow_call
invocations and evaluates to empty string at runtime).

F4 (HIGH/C3): e3-workflow-selftest.yml's assert jobs that depend on
expected-FAILURE reusable-workflow invocations (assert-tampered-digest,
assert-expired) must declare an `if:` condition that allows them to run when
the upstream reusable-workflow job FAILS — otherwise they skip silently,
masking whether the AEGIS-taxonomy error_class actually surfaced.

Run: pytest tests/test_workflow_invariants.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REUSABLE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "aegis-verify-attestation.yml"
SELFTEST_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "e3-workflow-selftest.yml"


class TestReusableWorkflowF1F2Regression:
    """Phase 2 cycle 1 F1+F2 regression — invalid context variable."""

    def test_reusable_workflow_checkout_uses_workflow_sha(self):
        """The inner actions/checkout step MUST resolve to the caller's pinned ref
        via `${{ github.workflow_sha }}` — not `${{ github.event.workflow.ref }}`
        (which is not a documented context variable for workflow_call invocations
        and resolves to empty string, causing actions/checkout to fall back to
        the named repository's default branch — breaking the byte-exact
        key/policy/script consistency contract).
        """
        doc = yaml.safe_load(REUSABLE_WORKFLOW.read_text())
        # YAML 1.1 coerces `on:` → boolean True at top level
        on_block = doc.get(True) or doc.get("on")
        assert on_block is not None, "workflow_call trigger missing"
        assert "workflow_call" in on_block

        jobs = doc["jobs"]
        assert "verify" in jobs
        steps = jobs["verify"]["steps"]

        checkout_step = next(
            (s for s in steps if "actions/checkout" in s.get("uses", "")), None
        )
        assert checkout_step is not None, "no actions/checkout step found"
        ref_expr = checkout_step["with"]["ref"]
        assert ref_expr.strip() == "${{ github.workflow_sha }}", (
            f"checkout ref must be ${{{{ github.workflow_sha }}}}; got {ref_expr!r}. "
            f"See /quality-gate Phase 2 bug-hunt finding F1+F2."
        )

    def test_reusable_workflow_checkout_does_NOT_use_invalid_context(self):
        """Defensive check: explicitly reject the historical typo
        `github.event.workflow.ref` anywhere in the file (including comments
        that may have lingered)."""
        body = REUSABLE_WORKFLOW.read_text()
        # The fix DOES leave one explanatory reference in the comment block —
        # but it's prefixed by "an earlier plan-time draft used" indicating the
        # context. Verify the ref: line itself doesn't contain the invalid expr.
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("ref:") and "github.event.workflow.ref" in stripped:
                pytest.fail(
                    f"reusable workflow still uses invalid context variable in ref:; "
                    f"line: {stripped!r}"
                )


class TestSelftestWorkflowF4Regression:
    """Phase 2 cycle 1 F4 regression — assert-job skip semantics."""

    def test_assert_jobs_for_expected_failure_run_even_on_upstream_fail(self):
        """assert-tampered-digest + assert-expired depend on reusable-workflow
        invocations that intentionally return valid=false. The composite Action's
        verify_action.py exits 1 on valid=false → reusable workflow's `verify`
        job FAILS → these assert jobs SKIP by default. Must declare an `if:`
        condition (`always()`, `!cancelled()`, or `failure()`) to run anyway —
        otherwise the assertions never execute and the CI run shows a false
        green for the error_class taxonomy check.
        """
        doc = yaml.safe_load(SELFTEST_WORKFLOW.read_text())
        jobs = doc["jobs"]

        for assert_job_name in ("assert-tampered-digest", "assert-expired"):
            assert assert_job_name in jobs, f"{assert_job_name} missing"
            job = jobs[assert_job_name]
            if_clause = job.get("if", "")
            # Must contain a known "run-on-upstream-fail" expression so a failed
            # upstream job doesn't cause this assert to skip. Specifically:
            #   - `always()`      → runs always (incl. cancellation)
            #   - `!cancelled()`  → runs on success + failure, skips cancellation
            #   - `failure()`     → runs only on failure
            # `success()` is EXCLUDED — it would re-introduce the F4 bug
            # (assert would skip on upstream FAILED, defeating the purpose).
            # /quality-gate Phase 3 /ultrathink Probe 3 tightening.
            run_on_fail_patterns = ("always()", "!cancelled()", "failure()")
            assert any(p in if_clause for p in run_on_fail_patterns), (
                f"{assert_job_name} must declare `if:` with one of {run_on_fail_patterns} "
                f"so the assertion runs even when the upstream reusable-workflow "
                f"invocation fails (composite exits 1 on valid=false). "
                f"See /quality-gate Phase 2 bug-hunt finding F4 + Phase 3 ultrathink "
                f"Probe 3. Got if={if_clause!r}."
            )
            # Defensive: explicitly reject `success()` to prevent the F4
            # regression "if: success()" pattern from passing this test.
            assert "success()" not in if_clause, (
                f"{assert_job_name} must NOT use `success()` in its `if:` clause — "
                f"that would skip the assert when the upstream reusable-workflow "
                f"invocation FAILS, defeating the F4 fix. Got if={if_clause!r}."
            )

    def test_replay_second_keeps_step_level_continue_on_error(self):
        """selftest-replay-second invokes the composite Action at STEP level
        (one indirection below the reusable workflow). It MUST keep
        `continue-on-error: true` on the verify step so the assert step in the
        same job can read outputs. This is the E2-pattern; verify it didn't
        regress during F4 remediation."""
        doc = yaml.safe_load(SELFTEST_WORKFLOW.read_text())
        steps = doc["jobs"]["selftest-replay-second"]["steps"]
        verify_step = next(
            (s for s in steps if s.get("id") == "verify"),
            None,
        )
        assert verify_step is not None
        assert verify_step.get("continue-on-error") is True, (
            "selftest-replay-second's composite-action invocation must keep "
            "`continue-on-error: true` so the assert step in the same job can "
            "read failure outputs."
        )


class TestSlsaUrlF8Regression:
    """Phase 2 cycle 1 F8 regression — dead slsa.dev URL."""

    def test_reusable_workflow_md_uses_valid_byob_url(self):
        """REUSABLE-WORKFLOW.md References section must not link to the dead
        `slsa.dev/spec/v1.0/use-cases-build-tool-reusable-workflow` URL.
        Correct citation is `github.com/slsa-framework/slsa-github-generator/
        blob/main/BYOB.md`."""
        md_path = REPO_ROOT / "actions" / "verify-aegis-attestation" / "REUSABLE-WORKFLOW.md"
        body = md_path.read_text()
        assert "slsa.dev/spec/v1.0/use-cases-build-tool-reusable-workflow" not in body, (
            "REUSABLE-WORKFLOW.md still links to the dead slsa.dev URL. "
            "Replace with BYOB.md per /quality-gate Phase 2 bug-hunt F8."
        )
        # Affirmatively check the new canonical URL is present
        assert "slsa-github-generator/blob/main/BYOB.md" in body

    def test_changelog_md_uses_valid_byob_url(self):
        """CHANGELOG.md [1.2.0] entry's Upstream references must use the same
        valid BYOB URL — same dead URL appeared in both files; both must be
        fixed."""
        body = (REPO_ROOT / "CHANGELOG.md").read_text()
        assert "slsa.dev/spec/v1.0/use-cases-build-tool-reusable-workflow" not in body
