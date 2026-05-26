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
AI_SECOND_REVIEW_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ai-second-review.yml"


class TestReusableWorkflowF1F2Regression:
    """Phase 2 cycle 1 F1+F2 regression — invalid context variable.

    UPDATED 2026-05-19 (cosmic-flute §37.18 sub-phase 3a): the original positive
    assertion (`ref: ${{ github.workflow_sha }}`) is itself buggy in cross-repo
    workflow_call (resolves to CALLER's SHA per gh-aw #24918 — see §37.17
    root-cause analysis). The fix uses a 2-step resolve_callee → checkout
    pattern with job.workflow_sha primary + referenced_workflows API fallback.
    See TestCrossRepoCheckoutPattern below for the new assertion surface.

    These 2 tests are retained as defensive negative checks against historical
    typos:
      - `github.event.workflow.ref` (the original E3 Phase 2 F1+F2 typo)
      - `github.workflow_sha` (the §37.17 cross-repo bug)
    """

    def test_reusable_workflow_checkout_uses_resolve_callee_outputs(self):
        """The inner actions/checkout step MUST resolve to the callee's
        pinned ref via the resolve_callee step's outputs — NOT via the
        `github.workflow_*` context (which resolves to CALLER values in
        cross-repo workflow_call per gh-aw #24918).

        Per cosmic-flute §37.18.3 defense-in-depth pattern: resolve_callee
        step uses job.workflow_sha (primary, callee-scoped per Contexts
        reference §job) with referenced_workflows API fallback for GHES.
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
        # Whitespace-tolerant regex (was strict-equality `==`). Allows
        # semantically-equivalent variations like `${{  steps.resolve_callee.outputs.ref  }}`
        # with extra inner whitespace, which parse identically in GHA but
        # would have failed the previous byte-identical assertion.
        # /quality-gate QG-§37.18 Phase 2 cycle 1 finding F2.1 (MEDIUM/C3).
        import re as _re
        _ref_pattern = r"^\s*\$\{\{\s*steps\.resolve_callee\.outputs\.ref\s*\}\}\s*$"
        assert _re.search(_ref_pattern, ref_expr), (
            f"checkout ref must consume resolve_callee.outputs.ref; got {ref_expr!r}. "
            f"See cosmic-flute §37.18.3 + §37.17 cross-repo workflow_call bug."
        )

    def test_reusable_workflow_checkout_does_NOT_use_invalid_context(self):
        """Defensive check: explicitly reject historical typos on any `ref:`
        line — both `github.event.workflow.ref` (original E3 F1+F2 typo) AND
        `github.workflow_sha` (the §37.17 cross-repo bug). Comments may
        explain why these are wrong; the prohibition is only on `ref:` lines.
        """
        body = REUSABLE_WORKFLOW.read_text()
        bad_patterns = ("github.event.workflow.ref", "github.workflow_sha")
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped.startswith("ref:"):
                continue
            for bad in bad_patterns:
                if bad in stripped:
                    pytest.fail(
                        f"reusable workflow uses invalid context variable on ref: line. "
                        f"Pattern {bad!r} resolves to CALLER values in cross-repo "
                        f"workflow_call. Use steps.resolve_callee.outputs.ref instead. "
                        f"See cosmic-flute §37.17 + §37.18.3. Offending line: {stripped!r}"
                    )


class TestCrossRepoCheckoutPattern:
    """Sprint 6/F1 sub-phase 3a regression guard — cosmic-flute §37.17 + §37.18.

    The reusable workflow at .github/workflows/aegis-verify-attestation.yml
    MUST use the job.workflow_* context (or referenced_workflows API fallback)
    for self-checkout — NEVER the github.workflow_* context (which resolves
    to the CALLER's values in cross-repo workflow_call per gh-aw issue #24918).

    The bug was caught by Sprint 6/F1 sub-phase 3 dry-run RUN 25980426234
    (2026-05-17) when the verify job failed at actions/checkout with
    `fatal: remote error: upload-pack: not our ref`. See cosmic-flute §37.17
    for the root-cause analysis and §37.18.3 for the defense-in-depth fix.
    """

    def setUp(self):
        # pytest classes — setUp isn't called; use module-level constants.
        pass

    def test_uses_job_workflow_context_for_callee_resolution(self):
        """Primary path: job.workflow_* returns callee values per Contexts
        reference §job (GitHub.com cloud)."""
        wf = REUSABLE_WORKFLOW.read_text()
        assert "job.workflow_sha" in wf, (
            "Reusable workflow MUST reference job.workflow_sha (callee's SHA) "
            "in the resolve_callee step. See §37.18.3 primary resolution path."
        )
        assert "job.workflow_repository" in wf, (
            "Reusable workflow MUST reference job.workflow_repository "
            "(callee's owner/repo). See §37.18.3 primary resolution path."
        )

    def test_has_referenced_workflows_api_fallback(self):
        """Defense-in-depth: API fallback for GHES + future-proofing per
        gh-aw PR #24974 + canonical/get-workflow-version-action."""
        wf = REUSABLE_WORKFLOW.read_text()
        assert "referenced_workflows" in wf, (
            "Reusable workflow MUST have referenced_workflows API fallback "
            "for GHES compatibility. See §37.18.3 fallback resolution path."
        )
        # Substring with trailing paren disambiguates the actual CALL site from
        # mere comment/string mentions of the symbol. /quality-gate QG-§37.18
        # Phase 2 cycle 1 finding F2.9 (MEDIUM/C3).
        assert "getWorkflowRun(" in wf, (
            "API fallback MUST CALL github.rest.actions.getWorkflowRun(...). "
            "Substring `getWorkflowRun(` (with open-paren) is required to "
            "disambiguate from comments/string mentions that name the symbol "
            "without invoking it. See §37.18.3."
        )

    def test_top_level_permissions_includes_actions_read(self):
        """The referenced_workflows API fallback requires permissions:
        actions: read. Top-level (not job-level) per §37.18.11 L7."""
        doc = yaml.safe_load(REUSABLE_WORKFLOW.read_text())
        perms = doc.get("permissions", {})
        assert isinstance(perms, dict), (
            f"Top-level permissions MUST be a dict (not a wildcard string "
            f"like 'read-all'); got {type(perms).__name__}"
        )
        assert perms.get("actions") == "read", (
            f"Top-level permissions MUST include 'actions: read' for the "
            f"referenced_workflows API fallback. Got: {perms!r}. See §37.18.3."
        )
        assert perms.get("contents") == "read", (
            f"Top-level permissions MUST keep 'contents: read' (existing "
            f"requirement for actions/checkout). Got: {perms!r}"
        )

    def test_checkout_uses_resolved_outputs(self):
        """actions/checkout step's repository: + ref: MUST consume the
        resolve_callee step's outputs (not hardcoded values or github
        context)."""
        wf = REUSABLE_WORKFLOW.read_text()
        # repository: should reference steps.resolve_callee.outputs.repository
        repo_pattern = r"repository:\s*\$\{\{\s*steps\.resolve_callee\.outputs\.repository\s*\}\}"
        ref_pattern = r"ref:\s*\$\{\{\s*steps\.resolve_callee\.outputs\.ref\s*\}\}"
        import re as _re
        assert _re.search(repo_pattern, wf), (
            "Checkout step MUST consume steps.resolve_callee.outputs.repository. "
            "Hardcoding `undercurrentai/aegis-policy` would defeat the GHES "
            "API fallback path. See §37.18.3."
        )
        assert _re.search(ref_pattern, wf), (
            "Checkout step MUST consume steps.resolve_callee.outputs.ref. "
            "See §37.18.3."
        )

    def test_prefers_immutable_sha_over_ref_in_api_fallback(self):
        """Per gh-aw PR #24974 lesson: prefer referenced_workflows[].sha
        over .ref to resist branch drift during long-running jobs."""
        wf = REUSABLE_WORKFLOW.read_text()
        import re as _re
        # Match patterns like `matchingEntry.sha || matchingEntry.ref` with
        # flexible whitespace
        sha_first_pattern = r"matchingEntry\.sha\s*\|\|\s*matchingEntry\.ref"
        assert _re.search(sha_first_pattern, wf), (
            "API fallback MUST prefer matchingEntry.sha over matchingEntry.ref "
            "to resist branch drift (gh-aw PR #24974). See §37.18.3."
        )

    def test_github_script_pinned_by_sha(self):
        """The resolve_callee step's actions/github-script MUST be SHA-pinned
        (40-char hex, case-insensitive), NOT a floating tag like @v9.
        Floating-tag pins violate SLSA-L3 supply-chain hygiene — a malicious
        force-push to the tag would silently change the github-script body
        executed in this privileged workflow.

        Case-insensitive `[0-9a-fA-F]` per /quality-gate Phase 3 /ultrathink
        probe U5: Git accepts mixed-case SHAs; lowercase-only regex would
        false-negative on a tool that emits uppercase.

        /quality-gate QG-§37.18 Phase 2 cycle 1 finding F2.5 (HIGH/C3)
        + Phase 3 /ultrathink U5 (MEDIUM/C2) regex hardening.
        """
        import re as _re
        wf = REUSABLE_WORKFLOW.read_text()
        # Match `uses: actions/github-script@<40-char-hex-sha>` allowing
        # trailing whitespace + optional `  # v9.0.0` comment.
        sha_pin_pattern = r"uses:\s+actions/github-script@[0-9a-fA-F]{40}\b"
        assert _re.search(sha_pin_pattern, wf), (
            "actions/github-script MUST be SHA-pinned (40-char hex), NOT a "
            "floating tag like @v9 or @main. Floating tags are mutable and "
            "violate SLSA-L3 supply-chain hygiene. See §37.18.3 + "
            "https://docs.github.com/en/actions/security-for-github-actions/"
            "security-hardening-for-github-actions/security-hardening-for-github-actions"
        )

    def test_resolve_callee_emits_required_outputs(self):
        """The resolve_callee github-script body MUST emit both
        `core.setOutput('repository', ...)` and `core.setOutput('ref', ...)`.
        If either is renamed/removed, the downstream actions/checkout step
        receives empty values and SILENTLY falls back to the default branch
        (NOT the pinned SHA), breaking the byte-exact key/policy/script
        consistency contract.

        Regex matches BOTH single-quote `'repository'` and double-quote
        `"repository"` JS string literal forms — JS is quote-style tolerant
        and a future refactor using double quotes would be semantically
        identical but a strict single-quote substring match would fail.
        Per /quality-gate Phase 3 /ultrathink U1-2nd (MEDIUM/C3).

        /quality-gate QG-§37.18 Phase 2 cycle 1 finding F2.6 (HIGH/C3)
        + Phase 3 /ultrathink U1-2nd (MEDIUM/C3) quote-style tolerance.
        """
        import re as _re
        wf = REUSABLE_WORKFLOW.read_text()
        # Quote-style-tolerant match: ' or " around the output key.
        repo_pattern = r"""core\.setOutput\(\s*['"]repository['"]"""
        ref_pattern = r"""core\.setOutput\(\s*['"]ref['"]"""
        assert _re.search(repo_pattern, wf), (
            "resolve_callee MUST emit core.setOutput('repository', ...) "
            "(single or double quotes around 'repository'). "
            "Without it, actions/checkout would receive an empty `repository:` "
            "and fall back to the workflow's home repo — bypassing the "
            "callee-resolution contract. See §37.18.3."
        )
        assert _re.search(ref_pattern, wf), (
            "resolve_callee MUST emit core.setOutput('ref', ...) "
            "(single or double quotes around 'ref'). "
            "Without it, actions/checkout would receive an empty `ref:` and "
            "silently fall back to the default branch — NOT the caller-pinned "
            "SHA — breaking byte-exact key/policy/script consistency. "
            "See §37.18.3."
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

    def test_e3_selftest_has_actions_read_permission(self):
        """e3-workflow-selftest.yml MUST declare `actions: read` at the
        top-level permissions block.

        Defensive guard: the selftest currently uses LOCAL same-repo
        `./.github/workflows/aegis-verify-attestation.yml` references, so
        `job.workflow_*` populates correctly and the API fallback in
        aegis-verify-attestation.yml resolve_callee step does NOT fire — so
        `actions: read` is not strictly required for the selftest to PASS
        today. HOWEVER, if the selftest is ever refactored to invoke the
        reusable workflow via the cross-repo
        `undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<sha>`
        path (e.g., to validate cross-repo semantics from within this repo's
        CI), the API fallback path becomes reachable and WILL fail without
        `actions: read`. Adding the permission now matches the consumer-side
        declaration pattern documented in CHANGELOG [1.2.1] §"Consumer-facing
        notes (breaking change in permissions union)".

        /quality-gate QG-§37.18 Phase 2 cycle 1 finding F1.2 (MEDIUM/C2 —
        defensive after downgrade from initial HIGH/C3 classification).
        """
        doc = yaml.safe_load(SELFTEST_WORKFLOW.read_text())
        perms = doc.get("permissions", {})
        assert isinstance(perms, dict), (
            f"selftest top-level permissions MUST be a dict; got {type(perms).__name__}"
        )
        assert perms.get("actions") == "read", (
            f"e3-workflow-selftest.yml top-level permissions MUST include "
            f"'actions: read' (defensive — matches the consumer-side declaration "
            f"pattern required when the reusable workflow's API fallback fires). "
            f"Got: {perms!r}. See CHANGELOG [1.2.1] + cosmic-flute §37.18 QG F1.2."
        )
        assert perms.get("contents") == "read", (
            f"e3-workflow-selftest.yml top-level permissions MUST keep "
            f"'contents: read'. Got: {perms!r}"
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


class TestAiSecondReviewC5Regression:
    """Sprint 7/G1 C5 regression guard for empty-diff semantics."""

    def test_enforce_verdict_skips_empty_diff_in_all_reviewer_jobs(self):
        """All three reviewer jobs must skip Enforce verdict when diff_empty=true.

        If a reviewer job enforces verdict without this guard, an empty
        diff can fail closed due to missing verdict output even though there
        was nothing to review.
        """
        doc = yaml.safe_load(AI_SECOND_REVIEW_WORKFLOW.read_text())
        jobs = doc["jobs"]

        for job_name in ("gpt-review", "codex-review", "claude-review"):
            steps = jobs[job_name]["steps"]
            enforce = next((s for s in steps if s.get("name") == "Enforce verdict"), None)
            assert enforce is not None, f"{job_name} missing Enforce verdict step"
            if_clause = enforce.get("if", "")
            assert "steps.diff.outputs.diff_empty != 'true'" in if_clause, (
                f"{job_name} Enforce verdict must skip empty diffs "
                f"(missing `steps.diff.outputs.diff_empty != 'true'` in if: {if_clause!r})"
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
