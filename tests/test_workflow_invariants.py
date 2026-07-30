"""Static-validation tests for the Sprint 5/E3 workflow files.

These tests guard against /quality-gate Phase 2 bug-hunt findings (F1+F2+F4)
recurring silently. They parse the YAML statically rather than running the
workflows (which would require a live GitHub Actions run).

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

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REUSABLE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "aegis-verify-attestation.yml"
SELFTEST_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "e3-workflow-selftest.yml"
AI_SECOND_REVIEW_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ai-second-review.yml"
TESTS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
ERROR_CLASS_PARITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "error-class-parity.yml"
FINGERPRINT_PARITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "fingerprint-parity.yml"
ENFORCE_CALLER_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "aegis-enforce-caller.yml"
SHADOW_EVAL_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "aegis-shadow-eval.yml"
LINT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "lint.yml"
RESOLVE_CALLEE_PARITY_WORKFLOW = (
    REPO_ROOT / ".github" / "workflows" / "resolve-callee-parity.yml"
)
DEV_REQUIREMENTS = REPO_ROOT / "requirements-dev.txt"
CI_LOCKFILE = REPO_ROOT / "requirements-ci.txt"
AUX_REQUIREMENTS = REPO_ROOT / "requirements-aux.txt"
AUX_LOCKFILE = REPO_ROOT / "requirements-aux-ci.txt"
VERIFY_REQUIREMENTS = REPO_ROOT / "requirements-verify.txt"
VERIFY_LOCKFILE = REPO_ROOT / "requirements-verify-ci.txt"


def _executable_lines(text: str) -> str:
    """Workflow text with comment lines removed.

    Several assertions here prohibit a token whose PRESENCE in a comment is
    fine (usually the comment explaining why the token is banned). Stripping
    comment lines first keeps the prohibition aimed at what actually runs.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def _lockfile_logical_lines(text: str) -> list[str]:
    """requirements-ci.txt joined across backslash continuations.

    pip-compile writes one requirement per LOGICAL line:

        cffi==2.1.0 \\
            --hash=sha256:... \\
            --hash=sha256:...
            # via cryptography

    The trailing `# via` annotation is a plain comment line (no continuation
    reaches it) and is dropped like any other comment.
    """
    logical: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not buf and (not line.strip() or line.lstrip().startswith("#")):
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        logical.append((buf + line).strip())
        buf = ""
    if buf.strip():
        logical.append(buf.strip())
    return logical


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
        reference §job (GitHub.com cloud).

        Pins the ENV-WIRING SHAPE, not a raw substring: comments and a
        core.info() diagnostic string also contain the literal
        'job.workflow_sha', so a substring check stayed green when the actual
        wiring was mutated to github.workflow_sha — the exact §37.17 bug
        (v1.4.1 audit, mutation-verified)."""
        wf = REUSABLE_WORKFLOW.read_text()
        assert re.search(
            r"JOB_WORKFLOW_SHA:\s*\$\{\{\s*job\.workflow_sha\s*\}\}", wf
        ), (
            "resolve_callee env wiring MUST be "
            "`JOB_WORKFLOW_SHA: ${{ job.workflow_sha }}` — the callee-scoped "
            "context. github.workflow_sha resolves to CALLER values in "
            "cross-repo workflow_call. See §37.18.3."
        )
        assert re.search(
            r"JOB_WORKFLOW_REPOSITORY:\s*\$\{\{\s*job\.workflow_repository\s*\}\}", wf
        ), (
            "resolve_callee env wiring MUST be "
            "`JOB_WORKFLOW_REPOSITORY: ${{ job.workflow_repository }}`. "
            "See §37.18.3."
        )
        assert not re.search(
            r"JOB_WORKFLOW_(?:SHA|REPOSITORY):\s*\$\{\{\s*github\.", wf
        ), (
            "resolve_callee env wiring consumes the github.* context — the "
            "§37.17 cross-repo bug reintroduced at the wiring site."
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
            # Strip `!`-negated tokens first: `if: ${{ !failure() }}` CONTAINS
            # "failure()" yet reintroduces exactly the F4 skip-on-upstream-fail
            # semantics (v1.4.1 audit). Only un-negated occurrences count.
            unnegated = re.sub(r"!\s*(always|cancelled|failure)\(\)", "", if_clause)
            run_on_fail_patterns = ("always()", "!cancelled()", "failure()")
            assert (
                "always()" in unnegated
                or "!cancelled()" in if_clause
                or "failure()" in unnegated
            ), (
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


class TestTestsWorkflowInvariants:
    """`tests.yml` is now the gate for the API-key redaction guard.

    Every other workflow in this repo that carries a security property has its
    shape pinned here. This one had nothing, which meant the properties that
    make it trustworthy — least-privilege token, SHA-pinned actions, a bounded
    runtime, and an execution-based (not collection-based) guard assertion —
    could be edited away without a single test going red.
    """

    def test_permissions_are_read_only(self):
        doc = yaml.safe_load(TESTS_WORKFLOW.read_text())
        assert doc["permissions"] == {"contents": "read"}, (
            "tests.yml runs fork-authored code (pip install of a fork-controlled "
            "requirements file, then fork-controlled tests). Its token must stay "
            "read-only."
        )

    def test_uses_pull_request_not_pull_request_target(self):
        wf = TESTS_WORKFLOW.read_text()
        assert "pull_request_target" not in wf, (
            "pull_request_target would check out fork code under a privileged "
            "token on a PUBLIC repo — a critical vulnerability, not a trigger fix."
        )

    def test_actions_are_sha_pinned(self):
        wf = TESTS_WORKFLOW.read_text()
        # Hex-40, not \w{40}: a 40-char branch/tag NAME is mutable but matched
        # \w{40}, defeating the pin check (v1.4.1 audit). A git SHA is hex.
        unpinned = re.findall(r"uses:\s*(\S+@(?![0-9a-fA-F]{40}\b)\S+)", wf)
        assert not unpinned, f"unpinned actions in tests.yml: {unpinned}"

    def test_job_is_time_bounded(self):
        doc = yaml.safe_load(TESTS_WORKFLOW.read_text())
        assert "timeout-minutes" in doc["jobs"]["pytest"], (
            "Without timeout-minutes the default is 360 on a billed runner — "
            "the ceiling an unbounded subprocess would burn."
        )

    def test_guard_asserts_execution_not_collection(self):
        """The regression guard for this job's own core defect.

        The first version counted `pytest --collect-only` output. A module-level
        `pytest.mark.skip` produced "13 skipped", exit 0, a GREEN job, and a
        collected count of 13 — so the guard passed while every assertion it
        protects was disabled. Reading the JUnit XML step 1 produced is what
        distinguishes executed from merely collected.
        """
        wf = TESTS_WORKFLOW.read_text()
        executable = _executable_lines(wf)
        # BOTH jobs carry the guard pair — count, don't just detect: deleting
        # the verifier-kit job's entire guard step left the matrix job's copy
        # satisfying single-occurrence assertions while the 19
        # highest-severity tests lost their executed-count guard (v1.4.1
        # audit, mutation-verified). Comment-stripped so commentary can't
        # satisfy the positives.
        assert executable.count("--junitxml") == 2, (
            "BOTH the matrix suite step and the verifier-kit step must emit "
            "JUnit reports — one --junitxml per job."
        )
        assert executable.count('tc.find("skipped") is None') == 2, (
            "BOTH jobs must carry the executed-not-collected guard "
            "(<skipped/> exclusion) — a single copy means one job's tests "
            "can silently stop executing."
        )
        assert "--collect-only" not in executable, (
            "collection-based counting is the defect this step was rewritten to "
            "fix — a collected test can be a skipped test."
        )

    def test_sdk_needing_tests_are_partitioned_by_marker(self):
        """`--ignore=<path>` was replaced by a capability marker, and the two
        jobs must PARTITION the suite on it exactly.

        A path exclusion makes the NEXT SDK-needing test file turn the matrix
        job red-by-default, with the fix living in a workflow its author had
        no reason to open. And if the matrix deselect and the verifier-kit
        select ever use different marker expressions, tests fall in the gap
        and run zero times — the pre-#36 state, quietly reintroduced.

        (The marker was `needs_secrets` until 2026-07-29; renamed because the
        SDK has been public PyPI since 2026-05-15 and the secret it named
        never existed.)
        """
        # ALL assertions run comment-stripped — positives included. The
        # workflow's comments legitimately quote both marker expressions
        # (v1.4.0 audit reproduced this: with only the raw-text positives, a
        # deleted run line plus a surviving comment kept this test green
        # while the 19 highest-severity tests ran zero times, silently).
        executable = _executable_lines(TESTS_WORKFLOW.read_text())
        assert '-m "not needs_aegis_sdk"' in executable, (
            "the matrix job must deselect exactly the needs_aegis_sdk marker "
            "on an EXECUTABLE line (a comment quoting it does not count)"
        )
        assert re.search(r"-m needs_aegis_sdk\b", executable), (
            "the verifier-kit job must select exactly the needs_aegis_sdk "
            "marker on an EXECUTABLE line — the complement of the matrix "
            "deselect, so the two jobs partition the suite and nothing runs "
            "zero times"
        )
        assert "needs_secrets" not in executable, (
            "the retired marker name reasserts a false premise (a secret "
            "that never existed); use needs_aegis_sdk"
        )
        assert "--ignore=tests/" not in executable, (
            "path-based exclusion reintroduces the durability problem; declare "
            "the requirement on the test via the needs_aegis_sdk marker instead."
        )

    def test_matrix_does_not_cancel_siblings(self):
        """`fail-fast: false` became load-bearing when both matrix legs became
        required checks (org ruleset 16294975, 2026-07-29). With fail-fast true, a
        py3.12 failure CANCELS py3.13 on the same head SHA — and a `cancelled`
        required check blocks the merge while offering nothing to re-read or
        re-run in place."""
        doc = yaml.safe_load(TESTS_WORKFLOW.read_text())
        strategy = doc["jobs"]["pytest"].get("strategy", {})
        assert strategy.get("fail-fast") is False, (
            f"tests.yml matrix must set `fail-fast: false` explicitly (the GHA "
            f"default is true). Got strategy={strategy!r}. Both matrix legs are "
            f"required checks; letting one cancel the other wedges the PR."
        )


class TestRequiredCheckWorkflowsHaveNoPathsFilter:
    """Cosmic-flute §48.15 R2, enforced instead of remembered.

    A REQUIRED status check that never reports sits at "Expected" forever and
    the PR cannot merge. `aegis-enforce-caller.yml` has carried the rule as a
    comment since §48; the two parity workflows shipped WITH `paths:` filters
    anyway, which made every PR touching none of the filtered paths
    structurally unmergeable in-band — verified on #33 and #34 (docs-only) and
    #35 (workflow files outside the filter), each missing 2 of 5 required
    checks. That is the second, undiagnosed cause of the 32+ break-glass
    cycles; the code-owner gap was never the whole story.

    Every workflow feeding a required context in org ruleset 16294975 or
    17101026 is pinned here: its `pull_request` trigger must be UNFILTERED.
    """

    REQUIRED_CHECK_WORKFLOWS = [
        TESTS_WORKFLOW,             # Test suite (py3.12) / (py3.13)   [16294975]
        ERROR_CLASS_PARITY_WORKFLOW,   # SDK ↔ policy error_class parity  [16294975]
        FINGERPRINT_PARITY_WORKFLOW,   # keys/ ↔ required_keyids parity   [16294975]
        SHADOW_EVAL_WORKFLOW,       # AEGIS Shadow Evaluation           [16294975]
        LINT_WORKFLOW,              # Markdown lint + YAML lint + parse [16294975]
        ENFORCE_CALLER_WORKFLOW,    # aegis-gate / AEGIS Governance Gate [17101026]
    ]

    @pytest.mark.parametrize(
        "wf_path", REQUIRED_CHECK_WORKFLOWS, ids=lambda p: p.name
    )
    def test_pull_request_trigger_is_unfiltered(self, wf_path):
        doc = yaml.safe_load(wf_path.read_text())
        # YAML 1.1 coerces `on:` → boolean True at top level
        on_block = doc.get(True) or doc.get("on")
        assert on_block is not None, f"{wf_path.name}: no trigger block"
        if isinstance(on_block, list):
            assert "pull_request" in on_block
            return  # list form cannot carry filters
        assert "pull_request" in on_block, f"{wf_path.name}: no pull_request trigger"
        pr_trigger = on_block["pull_request"] or {}
        for forbidden in ("paths", "paths-ignore"):
            assert forbidden not in pr_trigger, (
                f"{wf_path.name} filters its pull_request trigger with "
                f"`{forbidden}:`. This workflow feeds a REQUIRED status check; "
                f"on a PR that matches no path it never reports, the check "
                f"sits at 'Expected' forever, and the PR is unmergeable "
                f"in-band (§48.15 R2 — the #33/#34/#35 wedge). Run the job "
                f"unconditionally; it is cheap and its assertion is a "
                f"repo-state invariant."
            )


class TestCiInstallsArePinned:
    """Every CI dependency install is a lockfile, not a live resolution.

    Six workflows install Python packages on `pull_request`. Each must install
    its hash-pinned lockfile with `--no-deps --require-hashes
    --only-binary=:all:`, never an open-range requirements file, and never an
    unpinned `pip install --upgrade pip`. Two failure classes closed: upstream
    drift (a new release inside an open range adopted by every PR at once —
    the aegis-governance ruff-0.16.0 incident) and quiet dependency swaps in
    PRs that look like they touch nothing. `--only-binary` closes a third,
    subtler one: pip's hash-checking mode accepts a HASHED SDIST when no
    compatible wheel exists, then fetches its build dependencies from live
    PyPI unpinned — reproduced during the v1.4.0 audit. See the lockfile
    headers for what this deliberately does NOT claim to stop (a fork editing
    a lockfile or workflow itself).

    KNOWN RESIDUAL, deliberate: ai-second-review.yml's reviewer lane installs
    `openai>=2.11` unpinned. That lane is advisory (`continue-on-error`),
    feeds no required check, and is rebuilt whenever the OpenAI account is
    refunded — pin it when it next matters. e2-action-selftest.yml is
    workflow_dispatch-only (not a PR surface) and is being retired.
    """

    # (workflow, lockfiles its jobs may install — tests.yml has TWO: the
    # matrix job's requirements-ci.txt and the verifier-kit job's
    # requirements-verify-ci.txt)
    INSTALLING_WORKFLOWS = [
        (TESTS_WORKFLOW, ("requirements-ci.txt", "requirements-verify-ci.txt")),
        (ERROR_CLASS_PARITY_WORKFLOW, ("requirements-ci.txt",)),
        (FINGERPRINT_PARITY_WORKFLOW, ("requirements-ci.txt",)),
        (LINT_WORKFLOW, ("requirements-aux-ci.txt",)),
        (SHADOW_EVAL_WORKFLOW, ("requirements-aux-ci.txt",)),
        (RESOLVE_CALLEE_PARITY_WORKFLOW, ("requirements-aux-ci.txt",)),
    ]

    # (human-readable source, compiled lockfile)
    LOCKFILE_PAIRS = [
        (DEV_REQUIREMENTS, CI_LOCKFILE),
        (AUX_REQUIREMENTS, AUX_LOCKFILE),
        (VERIFY_REQUIREMENTS, VERIFY_LOCKFILE),
    ]

    @pytest.mark.parametrize(
        "wf_path,lockfiles",
        INSTALLING_WORKFLOWS,
        ids=[p.name for p, _ in INSTALLING_WORKFLOWS],
    )
    def test_installs_from_hashed_lockfile_only(self, wf_path, lockfiles):
        """PER-COMMAND, not file-global: the v1.4.1 audit mutation-verified
        that whole-file substring checks pass when a SECOND unpinned install
        line is added (`pip install --upgrade setuptools`, `-U requests`,
        `-r requirements-extra.txt`) because the flags are satisfied by the
        legitimate line. Every pip-install command line must individually be
        a pinned install of one of the workflow's declared lockfiles."""
        executable = _executable_lines(wf_path.read_text())
        install_lines = re.findall(r"[^\n]*pip install[^\n]*", executable)
        assert install_lines, f"{wf_path.name}: no pip install line found"
        for line in install_lines:
            line = line.strip()
            hits_lockfile = any(
                re.search(rf"(?:-r|--requirement)[=\s]+\S*{re.escape(lf)}", line)
                for lf in lockfiles
            )
            assert (
                "--require-hashes" in line
                and "--no-deps" in line
                and "--only-binary=:all:" in line
                and hits_lockfile
            ), (
                f"{wf_path.name}: pip install line is not a pinned install of "
                f"one of {lockfiles} with --no-deps --require-hashes "
                f"--only-binary=:all: — every install must be a lockfile "
                f"closure, no side-channel installs. Offending: {line!r}"
            )
            assert not re.search(
                r"(?:-r|--requirement)[=\s]+\S*requirements-(?:dev|aux|verify)\.txt",
                line,
            ), (
                f"{wf_path.name} installs an open-range requirements SOURCE "
                f"file (live-PyPI resolution at run time): {line!r}"
            )
        assert "--upgrade pip" not in executable and "-U pip" not in executable, (
            f"{wf_path.name} upgrades pip from live PyPI — itself an "
            f"unpinned install of the exact class this step exists to close."
        )

    @pytest.mark.parametrize(
        "source,lockfile",
        LOCKFILE_PAIRS,
        ids=[s.name for s, _ in LOCKFILE_PAIRS],
    )
    def test_lockfile_covers_every_source_requirement(self, source, lockfile):
        """Drift guard: the source file is human-readable, the lockfile is
        compiled FROM it. Editing the source without regenerating would
        silently ship CI on stale pins; this fails until the two agree
        (regeneration command in each lockfile's header)."""
        from packaging.requirements import Requirement
        from packaging.utils import canonicalize_name
        from packaging.version import Version

        src_reqs = [
            Requirement(line.strip())
            for line in source.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert src_reqs, f"{source.name} parsed to zero requirements"

        pins: dict[str, Version] = {}
        for logical in _lockfile_logical_lines(lockfile.read_text()):
            m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==(\S+)", logical)
            if m:
                pins[canonicalize_name(m.group(1))] = Version(m.group(2))
        assert pins, f"{lockfile.name} parsed to zero pins"

        for req in src_reqs:
            name = canonicalize_name(req.name)
            assert name in pins, (
                f"{req.name} is in {source.name} but absent from "
                f"{lockfile.name} — regenerate the lockfile (command in "
                f"its header)."
            )
            assert str(pins[name]) in req.specifier, (
                f"{lockfile.name} pins {req.name}=={pins[name]}, outside "
                f"{source.name}'s range {req.specifier!s} — the two files "
                f"have drifted; regenerate the lockfile."
            )

    @pytest.mark.parametrize(
        "lockfile",
        [CI_LOCKFILE, AUX_LOCKFILE, VERIFY_LOCKFILE],
        ids=lambda p: p.name,
    )
    def test_every_lockfile_pin_carries_a_hash(self, lockfile):
        """`--require-hashes` aborts the whole install if ANY requirement
        lacks a hash — so an unhashed line is not a weaker pin, it is a
        broken CI install waiting for the next run. Catch it here instead."""
        unhashed = [
            logical.split()[0]
            for logical in _lockfile_logical_lines(lockfile.read_text())
            if re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*==", logical)
            and "--hash=sha256:" not in logical
        ]
        assert not unhashed, (
            f"{lockfile.name} pins without a --hash=sha256 digest: "
            f"{unhashed}. Regenerate with pip-compile --generate-hashes "
            f"(command in the lockfile header)."
        )


class TestRequiredCheckJobsAreTimeBounded:
    """Every required-check job runs on EVERY PR now (the paths filters are
    gone), so an unbounded hang burns the 360-minute GitHub default on a
    billed Blacksmith runner per occurrence. tests.yml learned this at #36;
    the audit found the parity/lint/shadow jobs had not."""

    WORKFLOWS = [
        TESTS_WORKFLOW,
        ERROR_CLASS_PARITY_WORKFLOW,
        FINGERPRINT_PARITY_WORKFLOW,
        SHADOW_EVAL_WORKFLOW,
        LINT_WORKFLOW,
        RESOLVE_CALLEE_PARITY_WORKFLOW,
    ]

    @pytest.mark.parametrize("wf_path", WORKFLOWS, ids=lambda p: p.name)
    def test_every_steps_job_sets_timeout_minutes(self, wf_path):
        doc = yaml.safe_load(wf_path.read_text())
        for job_name, job in doc["jobs"].items():
            if "steps" not in job:
                continue  # reusable-workflow call jobs cannot set timeouts
            assert "timeout-minutes" in job, (
                f"{wf_path.name} job {job_name!r} has no timeout-minutes; "
                f"the default is 360 on a billed runner and this job runs "
                f"on every PR."
            )


class TestAggregatorAbsentLaneDiagnostics:
    """A dead reviewer lane must SAY it is dead — with the step's own outcome.

    Reviewer jobs are `continue-on-error: true`, so `needs.*.result` reports
    success even when the lane's infrastructure died; the old block reason
    ("absent (result=success, verdict=<empty>)") named nothing. That opacity
    has a documented cost: four consecutive identical OpenAI-lane failures
    were read as model noise while the actual cause — an unfunded platform
    account — sat unread in the step log (#35's fix narrative). #35 wired the
    step outcome into placeholder PROSE only — one step short of the
    aggregator. These pins keep the durable wire in place; the decision stays
    fail-closed, only the diagnosis is load-bearing here.
    """

    REVIEW_STEP_IDS = {
        "gpt-review": "gpt",
        "codex-review": "codex",
        "claude-review": "claude",
    }

    def test_lint_workflow_guards_codeowners_validity(self):
        """Team-based CODEOWNERS lines are enforced only while the team
        exists and holds write access — org state outside git. If either
        lapses, GitHub silently falls back to the `*` line (machine-user
        included). The lint workflow's required job must assert the
        codeowners/errors API is empty so the downgrade is a red X."""
        executable = _executable_lines(LINT_WORKFLOW.read_text())
        assert "codeowners/errors" in executable, (
            "lint.yml must call repos/{repo}/codeowners/errors — without it, "
            "team deletion/rename/access-revocation silently hands trust-spine "
            "ownership to the `*` line."
        )
        wf = LINT_WORKFLOW.read_text()
        assert 'get("errors"' in wf, (
            "the guard must parse the errors array from the API response"
        )
        # Pin the FAIL behavior, not just the parse: a mutation downgrading
        # the non-empty branch to log-only kept the old assertions green
        # while the downgrade detection became advisory (v1.4.1 audit).
        assert re.search(r"if errors:[\s\S]{0,600}?sys\.exit\(1\)", wf), (
            "the guard must sys.exit(1) on a non-empty errors array — "
            "logging the downgrade without failing the required check is "
            "exactly the silent-lapse this guard exists to prevent."
        )

    def test_each_reviewer_job_exports_its_review_step_outcome(self):
        doc = yaml.safe_load(AI_SECOND_REVIEW_WORKFLOW.read_text())
        for job_name, step_id in self.REVIEW_STEP_IDS.items():
            outputs = doc["jobs"][job_name].get("outputs", {})
            expr = outputs.get("step_outcome", "")
            assert f"steps.{step_id}.outcome" in expr, (
                f"{job_name} must export step_outcome from its review step "
                f"(steps.{step_id}.outcome); got {expr!r}. Without it the "
                f"aggregator is back to 'absent (result=success)' blindness."
            )

    def test_aggregator_consumes_step_outcome_in_block_reason(self):
        wf = AI_SECOND_REVIEW_WORKFLOW.read_text()
        # Lane identity pinned exactly: cross-wiring (GPT_STEP fed from
        # claude-review) would report the WRONG lane's outcome — worse than
        # no diagnosis, because it reads as authoritative.
        for env_var, job in (
            ("GPT_STEP", "gpt-review"),
            ("CODEX_STEP", "codex-review"),
            ("CLAUDE_STEP", "claude-review"),
        ):
            assert re.search(
                rf"{env_var}: \$\{{\{{ needs\.{job}\.outputs\.step_outcome \}}\}}", wf
            ), f"aggregator env must wire {env_var} from needs.{job}.outputs.step_outcome exactly"
        # Pin the actual consumption shape, not a substring: the diagnosis is
        # derived FROM r.stepOutcome and interpolated INTO the block reason.
        # (First cut asserted `"r.stepOutcome" in wf`, which a neutering edit
        # like `false && r.stepOutcome` satisfies — caught by its own
        # negative control.)
        assert re.search(
            r"const step =\s*\n?\s*r\.stepOutcome === 'success'", wf
        ), (
            "the aggregator must derive the diagnosis directly from "
            "r.stepOutcome — exporting the output without reading it "
            "reintroduces the #35 one-step-short failure."
        )
        assert "'skipped'" in wf and "SKIPPED" in wf, (
            "the diagnosis must handle outcome=skipped distinctly — the "
            "usual pre-step death (checkout/diff failure) SKIPS the if:-gated "
            "review step, and pointing the operator at a step with no log is "
            "a wrong diagnosis delivered confidently."
        )
        assert re.search(r"absent \(result=\$\{[^}]+\}, verdict=\$\{[^}]+\}; \$\{step\}\)", wf), (
            "the block reason must interpolate ${step} — deriving the "
            "diagnosis and then not printing it is the same one-step-short "
            "failure in different clothes."
        )


class TestSdkDefaultParity:
    """The consumer-facing aegis-sdk-version default is declared in TWO
    places — the composite action and the reusable verify workflow. The
    roadmap's own warning: a bump touching one site strands the other, and
    (verified in the v1.5.0 scoping) no test pinned either default. Equality
    — not a hardcoded version — is the invariant, so routine bumps don't
    churn this test but a strand fails it loudly."""

    def test_both_default_sites_agree(self):
        composite = yaml.safe_load(
            (REPO_ROOT / "actions" / "verify-aegis-attestation" / "action.yml").read_text()
        )
        reusable = yaml.safe_load(REUSABLE_WORKFLOW.read_text())
        c_default = composite["inputs"]["aegis-sdk-version"]["default"]
        on_block = reusable.get(True) or reusable.get("on")
        r_default = on_block["workflow_call"]["inputs"]["aegis-sdk-version"]["default"]
        assert c_default == r_default, (
            f"aegis-sdk-version default STRANDED: composite action.yml says "
            f"{c_default!r} but the reusable workflow says {r_default!r} — "
            f"the two public surfaces must move together (docs/roadmap.md "
            f"two-site warning, now enforced)."
        )
        assert re.fullmatch(r"\d+\.\d+\.\d+", str(c_default)), (
            f"default must be an exact X.Y.Z pin, got {c_default!r}"
        )


class TestAggregatorReviewedSurfaceSubset:
    """A binding auto-approval requires changed-files ⊆ reviewed surface.

    The three reviewers only see the GATED_PATHS diff; without the subset
    rule a PR bundling a reviewed file with a file OUTSIDE both GATED_PATHS
    and the trust-spine carve-out (e.g. a new root conftest.py) would be
    machine-approved with zero eyes on the unreviewed file (v1.4.1 audit,
    HIGH). These pins keep the rule and its blocking teeth in place."""

    def test_gate_blocks_on_files_outside_reviewed_surface(self):
        wf = AI_SECOND_REVIEW_WORKFLOW.read_text()
        assert "REVIEWED_SURFACE" in wf and "const unreviewed = changed.find" in wf, (
            "the aggregator must compute the unreviewed set from the changed "
            "files against REVIEWED_SURFACE"
        )
        assert re.search(
            r"if \(unreviewed\) \{\s*\n\s*return decide\('block'", wf
        ), (
            "a changed file outside the reviewed surface must BLOCK the "
            "auto-approval — anything weaker approves code sight-unseen"
        )

    def test_reviewed_surface_mirrors_gated_paths(self):
        """The JS REVIEWED_SURFACE list must contain every GATED_PATHS entry
        (env block), so the subset rule and the diff surface can't drift."""
        wf = AI_SECOND_REVIEW_WORKFLOW.read_text()
        # [ \t]+ not \s+ — \s crosses the blank line at the end of the block
        # scalar and swallows the next top-level keys (jobs:, gpt-review:).
        m = re.search(r"GATED_PATHS: >-\n((?:[ \t]+\S+\n)+)", wf)
        assert m, "GATED_PATHS env block not found"
        gated = m.group(1).split()
        js = re.search(r"const REVIEWED_SURFACE = \[([\s\S]*?)\];", wf)
        assert js, "REVIEWED_SURFACE array not found"
        js_entries = set(re.findall(r"'([^']+)'", js.group(1)))
        missing = [g for g in gated if g not in js_entries]
        assert not missing, (
            f"GATED_PATHS entries missing from REVIEWED_SURFACE: {missing} — "
            f"the subset rule would spuriously block (or, if widened the "
            f"other way, silently approve) on drifted entries."
        )


class TestAggregatorRenameCoverage:
    """The trust-spine carve-out must see BOTH sides of a rename.

    GitHub's listFiles returns a renamed file as ONE entry whose `filename`
    is the NEW path; the old path is only in `previous_filename`. Mapping
    only `filename` made the carve-out rename-blind: renaming pytest.ini or
    a lockfile to an unprotected name matched no glob and fell to the `*`
    CODEOWNERS line where the machine-user IS a code owner (v1.4.0 audit).
    The aggregator now flatMaps `previous_filename` into the changed set;
    this pins that it stays."""

    def test_changed_files_include_previous_filename(self):
        wf = AI_SECOND_REVIEW_WORKFLOW.read_text()
        assert "previous_filename" in wf, (
            "ai-second-review.yml's aggregator must include "
            "f.previous_filename in the changed-files set — without it a "
            "rename-away of a bare-filename trust-spine entry is invisible "
            "to the carve-out (layer 1) and lands on the `*` CODEOWNERS "
            "line (layer 2)."
        )
        # Pin the EMITTING array, not mere proximity: a mutation keeping
        # previous_filename in the ternary CONDITION while dropping it from
        # the emitted array (`f.previous_filename ? [f.filename] : ...`)
        # satisfied the old proximity regex while reintroducing full
        # rename-blindness (v1.4.1 audit, mutation-verified).
        assert re.search(r"\[\s*f\.filename\s*,\s*f\.previous_filename\s*\]", wf), (
            "the rename branch must EMIT both paths — "
            "[f.filename, f.previous_filename] — consuming previous_filename "
            "in a condition without emitting the old path is rename-blindness "
            "in different clothes."
        )
