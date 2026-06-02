# AEGIS Policy Changelog

All notable changes to the `undercurrentai/aegis-policy` repo. Format: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

This is the **repo-level** changelog. The `policy_version` field of `policy/verifier-policy-v1.yaml` is tracked separately in `policy/CHANGELOG.md`.

---

## [1.2.6] — 2026-06-02

**Sprint 7/G1 §51 — cross-repo `./` resolve_callee fix for the enforce substrate + bundled pre-G2-contract-hardening (closes 20 of the 22 §48.17 deferrals).** The load-bearing G2 prerequisite (cosmic-flute §48.16.3): `uses: ./.github/actions/aegis-gate` inside the `aegis-enforce.yml` reusable workflow resolved against the CALLER's checked-out workspace, not aegis-policy's — the same class as the §37.18 cross-repo `workflow_call` self-checkout bug. This blocked every cross-repo consumer (aegis-governance SP1 cross-repo repoint + all G2/G3 rollout). Fixed by porting the §37.18 `resolve_callee` pattern (parameterized via a single shared `.github/scripts/resolve_callee.mjs`, byte-mirrored into both reusable workflows' inline `script:` bodies + Node-test-covered) + a checkout-aegis-policy-to-`path:` step, so the composite resolves as `./aegis-policy/.github/actions/aegis-gate` from any caller. Bundled with the 20 pre-G2-contract-hardening findings from the §48.17 post-ship audit — the cheapest moment to make input-contract changes is before the first G2 consumer copies the caller shape and before cutting `v1`. The 2 enforce-flip-governance findings (QG48-2 fail-open conclusionMap + QG48-16 confidence-never-gates) stay deferred — they're shadow→enforce-flip decisions, not contract hardening. Advisory only (`shadow_mode: true`) during the §48 calibration window; ZERO production runtime impact; verifier-kit (`aegis-verify-attestation.yml` + `verify_action.py` + `verify-aegis-attestation` composite) + its cross-repo consumer pin UNCHANGED.

### Added

- **`.github/scripts/resolve_callee.mjs`** (NEW) — single canonical `resolve_callee` resolver shared by BOTH reusable workflows (`aegis-verify-attestation.yml` + `aegis-enforce.yml`) via a `REUSABLE_WORKFLOW_FILENAME` env parameter; the Node test harness imports it and the `resolve-callee-parity.yml` gate byte-mirrors it against each workflow's inline `script:` body.
- **`aegis-enforce.yml` resolve_callee + checkout-to-path** — `job.workflow_repository`/`job.workflow_sha` PRIMARY on cloud + `referenced_workflows` API FALLBACK on GHES → checks out aegis-policy to `path: aegis-policy` → `uses: ./aegis-policy/.github/actions/aegis-gate`. `actions: read` added to the reusable + caller permissions for the API fallback.
- **`tests/test_verify_attestation_node.mjs`** — extended to 9 tests (test 8 = `REUSABLE_WORKFLOW_FILENAME=aegis-enforce.yml` targets the enforce consumer; test 9 = missing-env guard throws). `resolve-callee-parity.yml` extended to byte-diff BOTH workflows' inline bodies against the `.mjs`.
- **`docs/release-discipline.md`** (NEW) — consumer-pinning contract + SemVer→impact mapping + `v1` moving-tag plan (closes QG48-D5). The first `v1` tag is established at the §51 ship.

### Changed

- **`.github/actions/aegis-gate/action.yml` marked INTERNAL-only** (QG48-D1) — the reusable workflow is now the single supported public entry point; the composite carries bare-minimum defaults + is invoked only by `aegis-enforce.yml`. Collapses the default-divergence / required+default / alias-asymmetry / complexity-floor footguns (D1/D2/D4/D7) to "don't consume the composite directly".
- **`aegis-enforce.yml` + `aegis-gate/action.yml` hardened** — random per-run GITHUB_OUTPUT heredoc delimiters (QG48-1); case-insensitive HALT compare (QG48-3); Bearer/key-token redaction + body truncation on non-200 public-log (QG48-4); dropped unused `pull-requests: write` (QG48-5); curl `--retry`/`--connect-timeout`/`--max-time` (QG48-6); errexit-safe curl rc + fail-closed on empty/non-200 (QG48-7); `.get('status','')` + empty-status fail-closed guard (QG48-8); per-invocation `mktemp` + EXIT-trap cleanup (QG48-9); STEP_SUMMARY markdown-cell escaping (QG48-10); `checks.create` → listForRef dedup + update-or-create + try/catch (QG48-11); explicit `AEGIS_API_KEY` secret in usage example + caller, not `secrets: inherit` (QG48-12); published Checks-API run renamed "AEGIS Governance (advisory verdict detail)" to disambiguate from the required `aegis-gate / AEGIS Governance Gate` (QG48-13); novelty derivation keyed to the `change_type` enum (QG48-D3); input surface documented as the canonical 1:1 passthrough to the internal composite schema (QG48-D8).
- **aegis-policy version 1.2.5 → 1.2.6** (PATCH per SemVer; CI-workflow + docs hardening; ZERO production runtime impact; verifier-kit + cross-repo consumer pin UNCHANGED).

### Deferred

- **QG48-2 + QG48-16** (fail-open conclusionMap; confidence-never-gates) — remain in the enforce-flip-governance-decision carrier per §48.17.2 (shadow→enforce-flip decisions, not §51 contract hardening). Tracked in `.quality-gate/accepted-findings.jsonl`.

Refs: cosmic-flute §51 + §48.16.3 (cross-repo `./` bug) + §48.17.2 (the 22-deferral carriers) + §37.18 (`resolve_callee` precedent).

## [1.2.5] — 2026-05-31

**Sprint 7/G1 SP2 — relocate the §48 enforce substrate to aegis-policy + local self-dogfood caller (shadow mode).** RELOCATION PIVOT: the §48 enforce substrate — the `aegis-enforce.yml` reusable workflow + the `aegis-gate` composite action — was relocated from PRIVATE `aegis-governance` to PUBLIC `aegis-policy`, which now hosts the single source of truth. Root cause: a PUBLIC caller repo cannot invoke a PRIVATE repo's reusable workflow (GitHub platform restriction; the callee's `access_level` does not override it; masks as the error "workflow was not found"). aegis-policy therefore consumes its own substrate LOCALLY via `uses: ./.github/workflows/aegis-enforce.yml` (the composite referenced as `./.github/actions/aegis-gate`); aegis-governance (private) + all future G2/G3 consumers will call it cross-repo via `undercurrentai/aegis-policy/…@<SHA>` (private/internal → public is ALLOWED). Supersedes PR #190's substrate location. Advisory only (`shadow_mode: true` → the reusable workflow's `continue-on-error: ${{ inputs.shadow_mode }}`) during the §48 calibration window — HALT does not block merge yet. ZERO production runtime impact; ZERO change to the verifier-kit (`aegis-verify-attestation.yml` + `verify_action.py` + the `verify-aegis-attestation` composite Action) or its cross-repo consumer pin.

### Added

- **`.github/workflows/aegis-enforce.yml`** (NEW; relocated from aegis-governance) — reusable workflow (`workflow_call`) wrapping the `aegis-gate` composite; job `aegis-gate` with `continue-on-error: ${{ inputs.shadow_mode }}` (shadow runs are advisory) references the composite locally as `./.github/actions/aegis-gate` and attaches the verdict as a Checks-API run via `actions/github-script`. Emits the resolved required-check `aegis-gate / AEGIS Governance Gate`.
- **`.github/actions/aegis-gate/action.yml`** (NEW; relocated from aegis-governance) — composite action (`AEGIS Governance Gate`) calling `POST ${AEGIS_API_URL}/evaluate` (default `https://api.aegis.undercurrentholdings.com`) with `Authorization: Bearer ${AEGIS_API_KEY}` over the 6 AEGIS quantitative gates; outputs `status`/`confidence`/`rationale`/`decision_json`; `fail_on_halt: ${{ inputs.shadow_mode == false }}` (HALT only blocks merge once enforcing).
- **`.github/workflows/aegis-enforce-caller.yml`** (NEW) — aegis-policy self-dogfood caller consuming the relocated substrate LOCALLY via `uses: ./.github/workflows/aegis-enforce.yml`. Job key `aegis-gate` (no `name:` field) resolves the required-check `aegis-gate / AEGIS Governance Gate` per GitHub Docs reusable-workflow naming (`<caller-job-id> / <reusable-job-name>`) — the uniform check string the org-Ruleset (id `17101026`, populated in §48 SP5) covers via the `aegis-enforce-mode` custom property across all Sprint 7 source + consumer repos (cosmic-flute §48/§48.16). Per §48.15 R2: NO `paths:` filter on `pull_request` (required checks must fire on every PR including docs-only PRs to avoid the "Waiting for status to be reported" merge-hang per community #54877). Per §48.15 R3: job key `aegis-gate` is byte-identical to the aegis-governance SP1 caller's job key so the resolved check name is uniform. Triggers on `pull_request` (branches `[main, master]`) + `merge_group`; concurrency `cancel-in-progress: true`; permissions `{contents: read, checks: write, pull-requests: write}` (the checks/PR-write grants are the reusable-workflow effective-perms INTERSECTION fix); `secrets: inherit`; inputs `shadow_mode: true`, `estimated_impact: medium`, `change_type: feature`, `agent_id: github-actions-aegis-policy-self-dogfood`.

### Changed

- **aegis-policy version 1.2.4 → 1.2.5** (PATCH per SemVer; additive CI workflow + relocated §48 substrate; ZERO production runtime impact; verifier-kit + its cross-repo consumer pin UNCHANGED).

### Deferred

- **Cross-repo repoint of aegis-governance** (consume aegis-policy's relocated reusable workflow via `undercurrentai/aegis-policy/…@<SHA>` + drop aegis-governance's local copy) is DEFERRED as a Sprint 7/G2 prerequisite — blocked on the cross-repo `./` action-resolution fix: `uses: ./.github/actions/aegis-gate` inside a reusable workflow resolves against the CALLER's checked-out workspace, not the callee repo (same class as the §37.18 cross-repo `workflow_call` self-checkout bug; caught via the closed PR #196). Fix = port the §37.18 `resolve_callee` pattern + a checkout-aegis-policy-to-path step into `aegis-enforce.yml`. See cosmic-flute §48.16.3.

### References

- cosmic-flute §48 (Sprint 7/G1 plan) + §48.15 (Ultraplan refinement: R1 measure-check-name, R2 no-`paths:`-filter, R3 uniform-job-key) + §48.16 (SP1-SP6 relocation-pivot ship capture).

---

## [1.2.4] — 2026-05-26

**Sprint 7/G1 task #185 — verifier-kit + tri-AI second-reviewer hardening bundle (11 deferred findings closed).** Closes the deferred-finding ledger from §37.18.16 (3 verifier-kit hardenings: F2.2 + U1+U2 + U9/F1.3) + §44.20.3 P1.5 baseline #1 (Codex C1+C2 + GPT G1+G2+G3+G4) + §44.20.10.2 P1.5 baseline #2 (NEW-H1 + NEW-H2 HIGH/C3). 5 prior /quality-gate Phase 2 bug-hunt cycles missed all 11 findings; the §44 tri-AI panel produced value single-pass review misses. Single PR + 5 commits + 6 files; ZERO production runtime impact; ZERO cross-repo aegis-governance consumer impact (consumer pin `cded778` unchanged).

### Security

- **Closes 11 deferred hardening items**: 2 HIGH/C3 (NEW-H1 `gh pr comment` shell-expansion; NEW-H2 Claude verdict-scrape spoofability) + 3 HIGH/C3 deferred verifier-kit semantics (F2.2 + U1+U2 + U9/F1.3 from §37.18.16) + 6 MEDIUM/C2-LOW/C2 (Codex C1+C2 + GPT G1-G4 from §44.20).
- **Dual-checkout BASE/HEAD pattern** (closes Codex C1 + GPT G1 + partial G3): trusted scripts execute from `base.sha` workspace (`aegis-policy-base/`); untrusted PR head fetched separately at `aegis-policy-pr/` with `persist-credentials: false` for diff DATA only. Eliminates the canonical "pwn request" attack pattern under `on: pull_request` per GitHub Security Lab 2021+2025 research. Diff anchored to **immutable `base.sha`** instead of mutable `base.ref` (closes Codex C1).
- **Artifact-based Claude verdict pipeline** (closes NEW-H2 HIGH/C3): Claude review parsed from local `claude_review.md` artifact in BASE workspace instead of PR-comment scrape. Eliminates spoofability + stale-run-prone races + entire comment-scrape attack surface. Comment posted via trusted `actions/github-script` `github.rest.issues.{createComment,updateComment}` with body passed via `process.env` (Octokit JSON-serializes; NEVER shell-evaluated). `Bash(gh pr comment:*)` removed from `claude_args.allowedTools` (closes NEW-H1 HIGH/C3 shell-expansion path).
- **Comment-pipeline integrity nonce**: `<!-- run-id:${GITHUB_RUN_ID} head-sha:${PR_HEAD_SHA} -->` stamped on every reviewer comment for observability cross-check + future replay detection.
- **Stale-SHA guard** (closes G2-residual MEDIUM/C2): `gpt-review` + `codex-review` + `claude-review` Enforce verdict steps gated on `env.STALE_RUN_BAIL != '1'`; preceding stale-SHA guard step uses `actions/github-script` to re-query PR head SHA and set bail flag on drift from compute-diff-time SHA. Defense-in-depth atop concurrency cancellation.
- **G3-symmetric fork-guard**: dual-checkout pattern preserves existing claude-review null-safe `head.repo` guard semantics; fork PRs cannot exercise secret-bearing steps (GitHub-platform default + explicit guard layer).
- **G4 truncation fail-closed gate**: 200 KB diff cap + REQUEST_CHANGES required when truncation occurs. Banner `[!!! diff truncated at 200 KB — fail-closed: REQUEST_CHANGES if you cannot verify the full surface !!!]` prepended to `pr_diff.patch` itself (models reading the diff see the directive directly); `Enforce verdict` step blocks merge if `diff_truncated=true` AND `verdict != REQUEST_CHANGES` — even APPROVE/COMMENT on a truncated diff is unsafe.
- **Codex sandboxing preamble** (closes Codex C2 MEDIUM/C2): `.github/codex/prompts/second-review.md` documents dual-checkout workspace boundary (`aegis-policy-base/`) + explicitly forbids `gh pr diff`, `gh pr view`, `curl`, `git fetch` to upstream. Claude `allowedTools` narrowed from generic `Read` to per-path scoped (`Read(../pr_diff.patch)`, `Read(keys/**)`, `Read(scripts/**)`, `Read(policy/**)`, `Read(docs/architecture/adr/**)`, `Read(.github/**)`). Removed `Bash(gh pr ...)` + `Bash(cat ...)` shell escape hatches.

### Added

- **`.github/scripts/resolve_callee.mjs`** (NEW; 160 LOC) — standalone ESM module mirroring inline github-script body for the resolve_callee step of `.github/workflows/aegis-verify-attestation.yml`. Parity-locked byte-for-byte against YAML inline body via dedicated CI workflow. Exports `resolve(github, context, core)` async function consumed by the Node test harness. Includes `REUSABLE_WORKFLOW_FILENAME` const + rebuilt `SELF_REGEX` via `new RegExp(...)` closure (closes U1+U2 rename hazard) + `core.warning` block on silent `.ref` fallback when `matchingEntry.sha` empty (closes U9/F1.3 observability gap).
- **`tests/test_verify_attestation_node.mjs`** (NEW; 246 LOC) — F2.2 Node test harness using `node:test` built-in test runner + mocked Octokit (`github.rest.actions.getWorkflowRun`) + mocked `core` closure. 7 tests covering: (1) primary `job.workflow_*` path; (2) fallback single-match `referenced_workflows-API` path; (3) fallback zero-match throws with disambiguation; (4) same-tuple multi-match resolves deterministically + emits `core.info`; (5) divergent-tuple multi-match throws with candidate enumeration; (6) SELF_REGEX forgery probe (`attacker/repo/.github/workflows/aegis-verify-attestation.yml.evil/inner.yml` does NOT match anchored regex); (7) U9 empty-`.sha` emits `core.warning` + falls back to mutable `.ref`. 7/7 PASS in ~47ms via `node --test`.
- **`.github/workflows/resolve-callee-parity.yml`** (NEW; 101 LOC) — PR-trigger CI workflow enforcing parity invariant between YAML inline `script:` body + `.mjs` body between `=== BEGIN_INLINE_PARITY ===` / `=== END_INLINE_PARITY ===` markers. Triggers on PRs touching `aegis-verify-attestation.yml`, `resolve_callee.mjs`, `test_verify_attestation_node.mjs`, or itself. Pipeline: Python+PyYAML extracts YAML inline body → `awk` extracts `.mjs` between markers → `diff` byte-for-byte → fail on mismatch → `node --test` 7/7 PASS. Runs on `blacksmith-4vcpu-ubuntu-2404` per portfolio convention. CANNOT live inside `aegis-verify-attestation.yml` itself (which is `workflow_call:`-only).

### Changed

- **aegis-policy version 1.2.3 → 1.2.4** (PATCH per SemVer; hardening + new test infrastructure; reusable workflow inputs/outputs UNCHANGED; cross-repo aegis-governance consumer pin at `cded778` unaffected).
- **`SELF_REGEX` filename literal extracted** to `REUSABLE_WORKFLOW_FILENAME = 'aegis-verify-attestation.yml'` const in both inline YAML script body + `.mjs` standalone module. Parity-locked via CI workflow.
- **`.github/workflows/aegis-verify-attestation.yml` resolve_callee step**: refactored `${{ toJSON(...) }}` template expressions to step-level `env:` block (`JOB_WORKFLOW_REPOSITORY` + `JOB_WORKFLOW_SHA`); body reads via `process.env.JOB_WORKFLOW_*` for clean stdlib-only execution path that mirrors the .mjs harness exactly.
- **Codex CLI prompt `Your environment` section**: documents post-C1 dual-checkout (`aegis-policy-base/` working directory; diff at `../pr_diff.patch`); replaces prior `./pr_diff.patch` path references.

### Wontfix / Deferred

- **G2 stale-SHA guard at Post-comment step**: only Enforce verdict step gated on `STALE_RUN_BAIL`. Stale comment-post is informational (last-writer-wins on PR API; doesn't block merge); stale enforce-exit-1 is the blocking concern. Defense-in-depth focuses on the gating concern; comment-pipeline can race within the cancellation window without blocking impact.
- **G4 banner instructions in 3 prompt sites** (gpt_review.py + second-review.md + claude inline prompt): banner prepended directly to `pr_diff.patch` is self-documenting (models reading diff see the directive); fail-closed Enforce verdict gate guarantees safety even if models miss the banner. Belt+suspenders prompt instructions deferred to Sprint 7/G1+ follow-up if observability data warrants.
- **Tri-AI panel composition** (gpt-5.4-pro + gpt-5.3-codex + claude-opus-4-6): inherits AIPEA source pattern. GPT-family over-representation (2/3 OpenAI) is documented limitation per cosmic-flute §44.17.1 model-diversity caveat. Future Sprint 7+ revisit alongside AIPEA upstream.
- **Strict 3-of-3 unanimous verdict requirement** for §44 Phase 2 aggregator-approve job (NOT shipped in §45): cosmic-flute §44.20.10.3 documents run-to-run non-determinism (P1.5 baselines #1+#2 on same PR produced 11 unique findings across 2 runs with ZERO overlap on most). Future Phase 2 design must address finding-class-agreement (NOT strict unanimous verdict) — separate task #265 area work.

### References

- cosmic-flute §45 (Sprint 7/G1 task #185 plan) + §45.12 (Ultraplan-refined execution detail) + §45.13 (post-merge ship capture; pending).
- cosmic-flute §44.20 (P1.5 baseline #1 + #2 findings + dual-checkout fix template).
- cosmic-flute §37.18.16 (3 deferred verifier-kit hardenings from QG-§37.18 post-ship audit).
- cosmic-flute §43.5 M1 + M3 + M5 institutional learning (run-verify scope probe + time-estimate buffers + recurrence tracking).
- GitHub Security Lab — Part 1 (2021) + Part 4 (2025): trusted assets + untrusted data under `on: pull_request`.
- Sysdig 2025-06-17 + Paul Serban 2025-12-23: `pull_request_target` security pitfalls (rejected as wrong mitigation per §44.20.4).

Closes cosmic-flute task #185.

---

## [1.2.3] — 2026-05-22

**Post-§38 roadmap content refresh** — `docs/roadmap.md` was 4 ship cycles behind canonical state per cosmic-flute §40 /discover audit C-FIND-G (HIGH × C3). Sub-phase 3a row still claimed "🟡 in-progress 2026-05-19 (THIS PR)" + sub-phases 3b/4/5 marked ☐ blocked/planned, despite all 4 having shipped 2026-05-19 plus §38 ADR-013 forensic-audit chain shipping 2026-05-21 (aegis-governance v1.2.7 production deploy). Standalone docs-PR per senior-eng decision: HIGH/C3 + PUBLIC security-spine artifact warrants immediate accuracy over bundle-into-#185-Sprint-7/G1 deferral. ZERO production impact; ZERO source-code touches.

### Changed

- **`docs/roadmap.md` table rows 13-15**: status flips reflecting cumulative ship state:
  - Sub-phase 3a: 🟡 in-progress → ✅ shipped 2026-05-19 (commit `c2ce026`); PR #11
  - Sub-phase 3b: ☐ blocked-by 3a → ✅ validated 2026-05-19 (aegis-governance RUN 26102961343; A6 Tier-4e canonical proof PASS valid=True for decision_id `9a181766-…`)
  - Sub-phase 4: ☐ blocked-by 3b → ✅ shipped 2026-05-19 (aegis-governance v1.2.6 production deploy; PR #182 squash-merge `8aa151d`; first non-dry-run attested deploy decision_id `52689bf3-…`; AEGIS Stage-2 decision_id `8e6a4573-…` PAUSE → override per §28.5.1)
  - Sub-phase 5: ☐ blocked-by 4 → ✅ shipped 2026-05-19 (Sprint 6/F1 SHIP COMPLETE; cosmic-flute §37.21 ship capture; memory breadcrumb bumped; cosmic-flute tasks #30 + #170 + #171 + #174 closed)
- **`docs/roadmap.md` Sprint 7 rows 18-20**: ☐ planned → 🟢 GREEN UNBLOCKED — planned (per cosmic-flute §38.13.7 + §27.15 post-ship disposition table; UNBLOCKED at architectural-contract layer). Sprint 7/G1 row clarified: attestation-stack-internal Ruleset (id 16294975, `aegis-*` repos) was already created during Sprint 5/E1.5 Phase 7 (2026-05-12); Sprint 7/G1 expands enforcement to the full 20-repo portfolio + ships deferred verifier-kit hardening bundle per cosmic-flute task #185.
- **`docs/roadmap.md` dependency graph (post-Sprint-6/F1-sub-phase-3a)**: extended downstream graph nodes from "Sprint 7/G1+G2+G3" placeholder to 4 NEW boxes — QG-§37.18 v1.2.2 patch (aegis-policy@cded778) → Sub-phase 4 v1.2.6 (aegis-governance@8aa151d) → §38 forensic-audit chain (aegis-governance@f012a33 / v1.2.7) → 🟢 Sprint 6/F2 + Sprint 7/G1 + G2 + G3 UNBLOCKED.

### Added

- **`docs/roadmap.md` 2 NEW table rows** for post-sub-phase-3a milestones missing from prior table state:
  - **QG-§37.18 post-ship audit** ✅ shipped 2026-05-19 (commit `cded778`, this repo's [1.2.2] patch) — PR #12 multi-match dedup + anchored SELF_REGEX + regression-test refinements + 8 LOW × C1/C2/C3 deferrals to Sprint 7/G1 task #185
  - **§38 (post-ship CTR-5/U3 closure + forensic-audit chain)** ✅ shipped 2026-05-21 (aegis-governance v1.2.7 production deploy) — cumulative 3-PR ship cycle: PR #183 (`c570505`) primary §38 + PR #184 (`25420ca`) PyPI 1.1.0 → 1.1.1 yanked-collision hotfix + PR #185 (`f012a33`) Attest job step-order hotfix. ADR-013 forensic-audit chain via `aegis_evaluate_decision_id` DB column (Option D — predicate UNCHANGED + envelope wire format BYTE-IDENTICAL with v1.2.6). aegis-sdk 1.1.1 LIVE on PyPI. aegis-policy main UNCHANGED at `cded778` (§38 D2-defer; Sprint 7/G1 task #185 picks up policy `informational_predicate_fields` update). Closes cosmic-flute tasks #196 + #197. See cosmic-flute §38.13. **§17 Critical 3 invariant `bypass_actors=[]` preserved across 9 cumulative sole-keyholder bypass cycles.**

### Wontfix (not addressed in this PR)

- `docs/roadmap.md:48-78:emoji-width-ascii-drift` cosmetic ASCII-art alignment in dep-graph boxes — `.quality-gate/accepted-findings.jsonl` row 2 already dispositions this as wontfix; not re-litigated.

### References

- cosmic-flute §40 — `/discover` execution 2026-05-22; C-FIND-G HIGH × C3 finding
- cosmic-flute §38.13 — §38 SHIP COMPLETE (forensic-audit chain)
- cosmic-flute §37.21 — Sprint 6/F1 SHIP COMPLETE
- cosmic-flute §37.18.14-§37.18.16 — sub-phase 3a ship + QG-§37.18 audit
- cosmic-flute §34.17.2 — sole-keyholder bypass cycle (10th reuse for this PR)

---

## [1.2.2] — 2026-05-19

**QG-§37.18 post-ship audit follow-ups** — closes 6 of 9 blocking findings from `/quality-gate` Phase 2 cycle 1 on aegis-policy@c2ce026 (cosmic-flute §37.18 sub-phase 3a). 3 deferred to accepted-findings.jsonl + Sprint 7/G1 verifier-kit hardening backlog. No behavior change for production consumers; tightens defense-in-depth + closes regression test coverage gaps.

### Changed

- **`.github/workflows/aegis-verify-attestation.yml` resolve_callee API fallback** (F1.1 MEDIUM/C2): replaced `referenced.find((wf) => wf.path.includes('/.github/workflows/aegis-verify-attestation.yml'))` substring filter + downstream `^([^/]+)/([^/]+)/` path regex with a single ANCHORED regex pass:

  ```javascript
  const SELF_REGEX = /^([^/]+)\/([^/]+)\/\.github\/workflows\/aegis-verify-attestation\.yml(?:@.*)?$/;
  ```

  Defense-in-depth against theoretical longer-path forgery (e.g., a malicious nested `attacker/repo/.github/workflows/aegis-verify-attestation.yml.evil/inner.yml` that would have matched the substring filter). Practical exploitability gated by GitHub's server-computed `referenced_workflows` shape, so this is forward-looking hardening.

- **`.github/workflows/e3-workflow-selftest.yml` permissions** (F1.2 MEDIUM/C2): added `actions: read` to top-level `permissions:` block. NOT strictly required today (selftest uses LOCAL same-repo `./.github/workflows/...` references, so `job.workflow_*` populates correctly and the API fallback path doesn't fire). Defensive add — matches the consumer-side declaration pattern documented in [1.2.1] §"Consumer-facing notes (breaking change in permissions union)" and prevents future regressions if the selftest is ever refactored to invoke cross-repo.

- **`tests/test_workflow_invariants.py` test_reusable_workflow_checkout_uses_resolve_callee_outputs** (F2.1 MEDIUM/C3): relaxed strict byte-identical equality (`==`) to whitespace-tolerant regex match. Previously, semantically-equivalent `${{  steps.resolve_callee.outputs.ref  }}` (extra inner whitespace) would have failed despite parsing identically in GHA.

- **`tests/test_workflow_invariants.py` test_has_referenced_workflows_api_fallback** (F2.9 MEDIUM/C3): tightened `"getWorkflowRun" in wf` to `"getWorkflowRun(" in wf` (with trailing paren). Disambiguates the actual call site from comments/string mentions of the symbol.

### Added

- **`tests/test_workflow_invariants.py::TestCrossRepoCheckoutPattern::test_github_script_pinned_by_sha`** (F2.5 HIGH/C3 regression guard): asserts `actions/github-script` is SHA-pinned (40-char hex regex), NOT a floating tag like `@v9`. Floating-tag pins violate SLSA-L3 supply-chain hygiene — a malicious force-push to the tag would silently change the github-script body executed in this privileged workflow.

- **`tests/test_workflow_invariants.py::TestCrossRepoCheckoutPattern::test_resolve_callee_emits_required_outputs`** (F2.6 HIGH/C3 regression guard): asserts the resolve_callee github-script body emits BOTH `core.setOutput('repository', ...)` and `core.setOutput('ref', ...)`. If either is renamed/removed, the downstream actions/checkout step receives empty values → silently falls back to the default branch (NOT the pinned SHA), breaking the byte-exact key/policy/script consistency contract WITHOUT test failure.

- **`tests/test_workflow_invariants.py::TestSelftestWorkflowF4Regression::test_e3_selftest_has_actions_read_permission`** (F1.2 MEDIUM/C2 regression guard): asserts e3-workflow-selftest.yml top-level `permissions:` declares `actions: read` (defensive — covers future cross-repo refactor).

- **`docs/roadmap.md` Sprint 6/F1 sub-phase 3a node in cumulative dep graph** (F3.3 MEDIUM/C3): added `Sprint 6/F1 sub-phase 3a (cross-repo workflow_call fix) → ✅ aegis-policy@c2ce026` between the E3 box and the Sprint 6/F1 dogfood line. Dep graph now accurately reflects the sub-phase chain.

### Forward-pointer (the [1.2.1] consumer-facing notice this entry adds context for)

Per [1.2.1] §"Consumer-facing notes (breaking change in permissions union)" — when **sub-phase 4** (aegis-governance v1.2.6 PR; task #174) updates `aegis-governance/.github/workflows/aegis-deploy.yml verify.uses` to pin aegis-policy@`c2ce026` (or this v1.2.2 successor), the PR MUST also add `actions: read` to either:
- the workflow-level `permissions:` block (alongside the existing `id-token: write` + `contents: read`), OR
- the `verify` job's permissions union (NOTE: reusable-workflow `uses:` jobs cannot declare job-level `permissions:` — must be at workflow level).

Without `actions: read`, the resolve_callee step's `referenced_workflows` API fallback (which fires when `job.workflow_*` are empty — e.g., on GHES or in future GitHub regressions) will return HTTP 403, and the verify job will fail. The PRIMARY `job.workflow_*` path on GitHub.com cloud does not need `actions: read`, so the perms-gap may go unnoticed under normal cross-repo invocation today — but the bug is latent.

This forward-pointer should have been included in [1.2.1] §"Consumer-facing notes" but was omitted; this [1.2.2] entry captures it for the audit trail. /quality-gate QG-§37.18 Phase 2 cycle 1 finding F3.5 (MEDIUM/C3).

### Deferred to accepted-findings.jsonl

1 blocking finding deferred per the QG-§37.18 audit disposition:

- **F2.2 HIGH/C3 — no runtime-semantics tests for the resolve_callee github-script body**. Substantive work requiring a Node test harness (mock `github.rest.actions.getWorkflowRun`, exercise empty/partial/multi-match referenced_workflows array shapes, exercise network-error paths, exercise `||` vs `&&` short-circuit semantics). Out of scope for this hotfix patch; bundle into Sprint 7/G1 verifier-kit hardening alongside task #154 (aegis-sdk 1.0.1 patch) + task #156 (compliance-nightly checkov).

Plus 2 NEW HIGH/C3 findings from /quality-gate Phase 3 /ultrathink (U1+U2) deferred as a single bundle:

- **U1+U2 HIGH/C3 — filename hardcoded in SELF_REGEX (rename hazard)** at `.github/workflows/aegis-verify-attestation.yml:251`. If this workflow file is ever renamed (e.g., for a future PQC algorithm migration), the API fallback throws "No referenced_workflows entry matched" permanently. Fix: extract filename to a const + add `test_self_regex_filename_matches_workflow_filename` asserting the literal matches `os.path.basename(REUSABLE_WORKFLOW)`. Low-likelihood trigger; bundle into Sprint 7/G1 hardening.

### Phase 3 /ultrathink remediations (NEW; bundled into this same v1.2.2 commit)

Pre-ship Phase 3 deep adversarial probe surfaced 10 NEW observations across IBM ODC trigger categories; 5 remediated in place, 2 deferred (U1+U2 above), 2 documented (U7, U8, U10 below), 1 wontfix (U4 Refs format on shipped commit message).

In-place fixes:

- **U5 MEDIUM/C2 — `test_github_script_pinned_by_sha` regex lowercase-only** at `tests/test_workflow_invariants.py:221`: relaxed `[0-9a-f]{40}` → `[0-9a-fA-F]{40}` to accept Git's case-insensitive SHAs (some tools emit uppercase).
- **U1-2nd MEDIUM/C3 — `test_resolve_callee_emits_required_outputs` quote-style brittleness**: replaced strict single-quote substring `"core.setOutput('repository'"` with quote-style-tolerant regex `core\.setOutput\(\s*['"]repository['"]`. Future maintainer using JS double-quotes `core.setOutput("repository", ...)` (semantically identical) no longer fails.
- **U6 MEDIUM/C2 — multi-match `for...of` non-determinism** at `.github/workflows/aegis-verify-attestation.yml:251-280`: replaced single-match-with-break loop with collect-all-matches + deduplication. If `referenced_workflows[]` contains multiple entries with the same path but different (owner,repo,sha) tuples (GitHub API ordering not guaranteed), the resolver now throws with disambiguation context rather than picking non-deterministically. Same-tuple duplicates resolve deterministically with `core.info` log.
- **U3 MEDIUM/C3 — CHANGELOG self-contradiction** (THIS section): "Deferred" list previously listed F1.1 + F2.9 as both fixed AND deferred. Cleaned up to cite only F2.2 as deferred (the actually-deferred item).
- **U10 MEDIUM/C2 — LOW disposition trail**: 14 LOW × C1/C2/C3 findings now enumerated below for audit trail.

Documentation-only updates (no code/test change):

- **U7 HIGH/C2 — Tier-4e re-validation requirement for sub-phase 4**: The canonical Tier-4e proof (§37.18.15) was executed on c2ce026's PRIMARY `job.workflow_*` path. Cycle-1 (332b999) + Phase 3 (this commit) modify the API fallback path only — the PRIMARY path bytes are unchanged. Production cloud invocations use the PRIMARY path, so the Tier-4e proof's transitive validity is preserved. HOWEVER, sub-phase 4 (aegis-governance v1.2.6 PR; task #174) MUST re-execute the §37.18.7 sub-phase 3b dry-run pattern against the new SHA pin (this v1.2.2 successor or its tag) as a formal re-validation gate BEFORE production traffic shift. The PRIMARY path is byte-identical so re-validation should pass on first attempt.
- **U8 MEDIUM/C2 — Transitive permissions for nested reusable-workflow chains**: The [1.2.1] §"Consumer-facing notes" warned DIRECT callers of aegis-policy to grant `actions: read`. For Sprint 7/G2-G3 19-repo rollout consumers who invoke aegis-policy from a workflow that is ITSELF invoked via `workflow_call` (nested chain), reusable-workflow permissions propagate downward only. The OUTERMOST caller must grant `actions: read` — nested intermediate workflows cannot elevate. Document this transitive-perms requirement in Sprint 7/G2-G3 rollout PRs.

### Wontfix (LOW disposition trail per U10)

14 LOW × C1/C2/C3 findings from QG-§37.18 Phase 2 are informational only (non-blocking per the confidence-gating rule in /quality-gate Output Normalization protocol — exit criterion blocks only on CRITICAL/HIGH/MEDIUM × C2+). Enumerated for audit completeness:

- F1.3 LOW/C2 (workflow): `getWorkflowRun` no try/catch — defense-in-depth observability gap
- F1.4 LOW/C1 (workflow): silent fallback to mutable `.ref` when `.sha` empty (re-probed at U9; LOW/C2 on second look but stays informational)
- F1.5 LOW/C1 (workflow): toJSON inline comment hardening (defense-in-depth note)
- F2.3 LOW/C2 (test): regex brittle to JS ternary/`??` refactors of `sha || ref`
- F2.4 LOW/C3 (test): empty `setUp(self): pass` no-op trap in pytest class
- F2.7 LOW/C2 (test): permissions test doesn't lock-down extra-keys (over-privilege via `id-token: write` etc.)
- F2.8 LOW/C2 (test): YAML 1.1 `on:` → bool coercion comment improvement
- F2.10 LOW/C3 (test): negative test brittle to multi-line YAML folded scalars (speculative)
- F2.11 LOW/C2 (test): inconsistent assert-message citation depth across TestCrossRepoCheckoutPattern
- F3.1 LOW/C3 (docs): docs/roadmap.md "PR #TBD" stale placeholder
- F3.2 LOW/C2 (docs): "EXECUTED-FAILED-GRACEFULLY" ad-hoc status not in legend vocabulary
- F3.4 LOW/C2 (docs): CHANGELOG missing structured `Refs:` footer per protocol
- F3.6 LOW/C3 (docs): ADR-001 Changelog row missing SHA/PR reference
- F3.7 LOW/C2 (docs): gh-aw #24918 vs #24949 relationship undocumented in ADR-001
- F3.8 LOW/C2 (docs): ADR-001 GHES-unavailability claim lacks specific citation
- U4 LOW/C3 (commit message): cycle-1 commit `Refs:` footer used shorthand `gh-aw#NNNN` not canonical `context7=…; exa=…` format. Wontfix (cannot amend shipped commit); future commits adhere.

Total: 16 entries (15 from Phase 2 + 1 from Phase 3 U4). All wontfix or informational; no follow-up PR planned. Re-elevate if production behavior surfaces a related issue.

### Verification chain

- pytest: 14/14 PASS in test_workflow_invariants.py (was 11; +3 NEW: test_github_script_pinned_by_sha + test_resolve_callee_emits_required_outputs + test_e3_selftest_has_actions_read_permission)
- pytest total: 34/34 PASS in tests/ dir (was 31; +3 new tests)
- error-class parity: 15-vs-15 unchanged (no taxonomy change)
- fingerprint parity: 2-vs-2 unchanged (no key rotation)
- YAML parse: clean
- yamllint -d relaxed: line-length warnings only (existing CI config)

### Upstream references

- Cosmic-flute plan §37.18 + §37.18.14 + §37.18.15: sub-phase 3a + 3b ship captures
- /quality-gate QG-§37.18: Phase 2 cycle 1 audit (this PR remediates 6 of 9 blocking findings)
- gh-aw issue #24918 + PR #24974 + #24200 + #24433 (Microsoft): cross-repo workflow_call lineage
- canonical/get-workflow-version-action: production composite pattern

---

## [1.2.1] — 2026-05-19

**Sprint 6/F1 sub-phase 3a hotfix** — closes cosmic-flute task #173. Root cause + fix documented in cosmic-flute §37.17 + §37.18.

### Fixed

- **HIGH/C3 cross-repo `workflow_call` self-checkout**: `.github/workflows/aegis-verify-attestation.yml` `actions/checkout` step used `ref: ${{ github.workflow_sha }}` to self-checkout the reusable workflow's source repo. In cross-repo `workflow_call` from a FOREIGN repo, `github.workflow_sha` resolves to the CALLER's commit SHA — NOT the callee's pinned SHA — per github/gh-aw issue #24918 (Microsoft, runtime debug output proof filed 2026-04-06). Result: `fatal: remote error: upload-pack: not our ref <caller-sha>`.

  The bug was caught by cosmic-flute §37 Sprint 6/F1 sub-phase 3 dry-run (aegis-governance RUN `25980426234`, 2026-05-17). All 4 prior jobs in the deploy pipeline PASSED; the canonical Tier-4e offline-verify proof with real pinned keys PASSED LOCALLY — the trust spine itself was intact. Only the verifier-kit's self-checkout step failed. Validates §17 Critical 3 dogfood-before-rollout pattern: the bug would have shipped to all 19 Sprint 7/G2-G3 consumers if not caught.

  **Fix** (defense-in-depth per cosmic-flute §37.18.3 + §37.18.11 L1):
  - **PRIMARY**: 2-step pattern with new `resolve_callee` step using `job.workflow_repository` + `job.workflow_sha`. These DO return callee values per GitHub Docs Contexts reference §job-context (GitHub.com cloud).
  - **FALLBACK**: `referenced_workflows` API via `actions/github-script@3a2844b7` (v9.0.0) calling `github.rest.actions.getWorkflowRun()` and reading `data.referenced_workflows[].sha` — preferring immutable SHA over mutable `ref` per github/gh-aw PR #24974 lesson. Works on GitHub Enterprise Server where `job.workflow_*` is unavailable.

  Pattern matches production-tested approaches in:
  - `canonical/get-workflow-version-action` (Apache-2.0; production since 2024)
  - Microsoft's `github/gh-aw` PRs #24200 + #24433 + #24974 (all 2026-04)

  Permissions delta: top-level `permissions:` block now includes `actions: read` (in addition to existing `contents: read`) for the API fallback. Per reusable-workflow propagation rules, callers MUST include `actions: read` in their workflow-level or job-level `permissions:` block.

### Added

- **`tests/test_workflow_invariants.py::TestCrossRepoCheckoutPattern`** — 5 new regression tests that catch the syntactic class of this bug:
  - `test_uses_job_workflow_context_for_callee_resolution` — asserts `job.workflow_sha` + `job.workflow_repository` present
  - `test_has_referenced_workflows_api_fallback` — asserts `referenced_workflows` + `getWorkflowRun` present
  - `test_top_level_permissions_includes_actions_read` — asserts `permissions: actions: read`
  - `test_checkout_uses_resolved_outputs` — asserts `repository:` + `ref:` consume `steps.resolve_callee.outputs.*`
  - `test_prefers_immutable_sha_over_ref_in_api_fallback` — asserts `matchingEntry.sha || matchingEntry.ref` pattern (gh-aw #24974 lesson)

- **`tests/test_workflow_invariants.py::TestReusableWorkflowF1F2Regression`** updated:
  - `test_reusable_workflow_checkout_uses_workflow_sha` → renamed/replaced with `test_reusable_workflow_checkout_uses_resolve_callee_outputs` — the previous positive assertion asserted the buggy `${{ github.workflow_sha }}` pattern as if it were correct. The new test asserts the corrected `${{ steps.resolve_callee.outputs.ref }}` pattern.
  - `test_reusable_workflow_checkout_does_NOT_use_invalid_context` extended — now rejects BOTH `github.event.workflow.ref` (original E3 F1+F2 typo) AND `github.workflow_sha` (the §37.17 cross-repo bug) on any `ref:` line. Comment-block mentions still permitted (used to explain the wrong patterns).

- **`docs/architecture/adr/ADR-001-repo-trust-model.md` §Decision subsection** — "Cross-repo workflow_call self-checkout: callee-context vs caller-context" (~60 lines) documenting the canonical 2025/2026 GitHub Actions semantics + the production discovery context. Status stays Accepted (additive implementation-level clarification, not a new architectural decision per ADR conventions).

### Consumer-facing notes (breaking change in permissions union)

- Callers invoking `uses: undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<NEW-SHA>` MUST add `actions: read` to their workflow-level or job-level `permissions:` block. Reusable-workflow `permissions:` are downgradable-only — the called workflow cannot grant itself more than the caller has. Existing callers with `permissions: contents: read` only will hit a runtime permission failure on the new resolve_callee step.

- Existing callers pinned to aegis-policy@`5b3e2c0` (E3 ship) or earlier are NOT affected until they bump to this v1.2.1 SHA. Sub-phase 4 (aegis-governance v1.2.6) will be the first consumer to bump.

### Verification chain

This PR's bug-discovery path is the canonical proof of the dogfood model:

1. Production /attest endpoint working (cosmic-flute §32.7 + §33.11.6 Tier 4c)
2. Pinned keys + offline verifier working (cosmic-flute §28.17 + §32.7 Tier 4e canonical proof)
3. Cross-repo `workflow_call` self-checkout BROKEN (this hotfix)

Items 1 + 2 are unchanged; item 3 is what's fixed. Trust spine (server-side issue + offline verify with real pinned keys) was provably intact throughout — only the verifier-kit's self-checkout failed.

### Upstream references

- Cosmic-flute plan §37.17: root-cause analysis from Sprint 6/F1 sub-phase 3 dry-run
- Cosmic-flute plan §37.18: this hotfix execution plan
- github/gh-aw issue #24918: <https://github.com/github/gh-aw/issues/24918>
- github/gh-aw PR #24974: <https://github.com/github/gh-aw/pull/24974>
- canonical/get-workflow-version-action: <https://github.com/canonical/get-workflow-version-action>
- GitHub Docs Contexts reference: <https://docs.github.com/en/actions/reference/workflows-and-actions/contexts>

---

## [1.2.0] — 2026-05-13

**Sprint 5/E3 ship** — closes cosmic-flute task #29 (reusable workflow) + bundles task #129 deferred E2 doc-flips per cosmic-flute §34.17.3.

### Added

- **`.github/workflows/aegis-verify-attestation.yml`** (reusable workflow). Job-level orchestration wrapper around the composite Action shipped in Sprint 5/E2 (commit `19a751e`). Triggered by `workflow_call:`. Consumers invoke at the JOB level via `uses: undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<sha>`. 12 inputs (9 standard: envelope / expected-digest / expected-environment / policy-version-expected / replay-store-path / python-version / aegis-sdk-version / aegis-sdk-git-ref / runs-on; plus 3 test-only: internal-fixture-mode / internal-keys-dir-override / internal-policy-path-override propagating via env: not with: per cosmic-flute §35.11 dec C). 1 optional secret AEGIS_SDK_FETCH_TOKEN. 9 outputs identical to the composite Action surface (two-stage indirection step → job.outputs → workflow_call.outputs). Single `verify` job: (1) `actions/checkout@de0fac2e` of aegis-policy at `github.workflow_sha` (ensures composite matches caller's `@<sha>` pin for byte-exact key/policy/script consistency — see §"Quality-gate hardening" below for the F1+F2 plan-time typo correction), (2) composite Action invocation forwarding all 8 standard inputs + test-only env vars + AEGIS_SDK_FETCH_TOKEN. Permissions: `contents: read` minimum (caller declares full union per reusable-workflow propagation rules).
- **`actions/verify-aegis-attestation/REUSABLE-WORKFLOW.md`** (~270 lines) — consumer-facing docs for the reusable workflow surface specifically. Sections: TL;DR, when-to-use-composite-vs-reusable decision matrix (industry precedent: SLSA-framework BYOB pattern, Tool Reusable Workflow wraps Tool Callback Action), full inputs tables (9 standard + 3 test-only), secrets propagation (explicit secrets: block vs `secrets: inherit`), outputs reference pattern (`needs.<job-id>.outputs.<X>`), permissions union pattern with link to GitHub Docs, worked example for deploy gate, worked example for risk-class downstream gate (env: propagation per GitHub Security Lab pattern; recommends `environment:` gating with required reviewers for high/critical), SHA-pinning expectations, versioning (3 knobs identical to composite — no new versioning surface).
- **`.github/workflows/e3-workflow-selftest.yml`** — `workflow_dispatch:`-only self-test for the reusable workflow. 9 jobs across 4 selftest+assert pairs: (1) happy-path → assert valid=true + replay-checked=true; (2) tampered-digest → assert AttestationDigestMismatch; (3) expired → assert AttestationExpired; (4) replay-detection split into 3 jobs (first-call → setup that uploads seeded replay store as `actions/upload-artifact` → second job downloads + invokes composite Action directly with seeded store → assert AttestationReplayDetected) — necessary split because GitHub job isolation prevents pre-seeding the runner-local replay store FROM a previous job's runner WITHIN a reusable-workflow invocation. The expected-FAILURE assert jobs (assert-tampered-digest + assert-expired) declare `if: ${{ !cancelled() }}` so they surface error_class assertions even when the upstream reusable-workflow `verify` job FAILS (per the F4 remediation captured in §"Quality-gate hardening" below). Reuses E2-shipped fixtures (tests/fixtures/envelope-*.json + test-keys/ + policy-test-v1.yaml). Activation path post-task-#59 PyPI publish identical to e2-action-selftest.
- **`tests/test_workflow_invariants.py`** — 6 regression tests across 3 classes guarding against Phase 2 bug-hunt findings recurring: `TestReusableWorkflowF1F2Regression` × 2 (asserts `github.workflow_sha` is the checkout ref + defensively rejects `github.event.workflow.ref`); `TestSelftestWorkflowF4Regression` × 2 (asserts assert-tampered-digest + assert-expired declare `if:` with `always()` | `!cancelled()` | `failure()` patterns + explicitly rejects `success()` per Phase 3 Probe 3 tightening; asserts selftest-replay-second's STEP-level `continue-on-error: true` preserved); `TestSlsaUrlF8Regression` × 2 (asserts REUSABLE-WORKFLOW.md + CHANGELOG.md use valid BYOB.md URL not the dead slsa.dev URL).

### Changed

- **`actions/verify-aegis-attestation/README.md`** (~20 LOC delta): added "## Reusable workflow alternative" section right after TL;DR with a 4-line invocation snippet + link to REUSABLE-WORKFLOW.md; replaced the stale "A future Sprint 5/E3 reusable workflow (task #29) will bundle this risk-class gating logic" footer (Sprint 5/E3 IS now this work) with a forward-link to REUSABLE-WORKFLOW.md §"Worked example: risk-class downstream gate".
- **`docs/roadmap.md`** (Sprint 5/E2 + E3 + dep graph) — bundled task #129 doc-flips per cosmic-flute §34.17.3:
  - Sprint 5/E2 row: 🟡 in-progress → ✅ shipped 2026-05-13 (commit `19a751e`); tracking column captures the in-flight CI job-name remediation `ff0ec71` + admin sole-keyholder pattern per cosmic-flute §34.17.2.
  - Sprint 5/E3 row: ☐ planned → 🟡 in-progress (this PR; merge SHA captured post-squash).
  - Dependency graph: E2's `<merge-sha-pending>` → `19a751e`; new E3 "THIS PR" box inserted; closing arrows simplified to linear flow into Sprint 6/F1+F2 + Sprint 7/G1+G2+G3.
- **`CHANGELOG.md` [1.1.0]** — added "### Post-merge notes" subsection documenting (a) the sustainable CI workflow job-name rename `ff0ec71` (resolves ruleset required_status_checks context-mismatch for the "AEGIS Shadow Evaluation" check), and (b) the transient OrganizationAdmin bypass cycle pattern per cosmic-flute §34.17.2 (operating pattern for sole-owner PRs until team grows beyond one engineer per ADR-001 documented growth path; bypass_actors=[] steady-state invariant per cosmic-flute §17 Critical 3 preserved).

### Notes

- **`policy/verifier-policy-v1.yaml` unchanged at v2.1.0** — no policy contract change. The reusable workflow is a thin orchestration wrapper; all crypto + fingerprint + replay-detection logic lives in the E2 composite Action (unchanged).
- **`scripts/_verify_local_vendored.py` unchanged** — vendored SDK source still pins `aegis-governance@dc9c9df` from the E2 ship.
- **Parity gates stay GREEN unchanged**: `check_error_class_parity.py` 15-vs-15 + `check_fingerprints.py` 2-vs-2. No taxonomy churn; no key rotation.
- **Sprint 6/F1 (task #30; aegis-deploy.yml dogfood)** is the next planned consumer of the reusable workflow surface, per cosmic-flute §35.12. CLAUDE.md §8 Ask-First gate applies — separate plan + PR on `aegis-governance`.

### Quality-gate hardening (Phase 2 + Phase 3 remediations)

Pre-ship `/quality-gate` 9-phase exhaustive run remediated 8 findings + added 6 regression tests + tightened 1 test post-Phase-3:

**Phase 2 /bug-hunt cycle 1 — 4 BLOCKING + 4 LOW remediated** (commit `a38cc73`):

- **F1+F2 HIGH/C3** (one root cause; 2 file manifestations): `aegis-verify-attestation.yml` line 180 used `github.event.workflow.ref` which is NOT a documented GitHub Actions context variable for `workflow_call:` invocations (cosmic-flute §35.4 propagated a plan-time typo). WebFetch of `docs.github.com/en/actions/reference/contexts-reference` 2026-05-13 confirmed canonical is `github.workflow_sha` ("The commit SHA of the workflow file that defines the current job") — for `uses: <repo>/<path>@<sha>`, resolves to exactly the SHA the caller pinned. Fixed both sites + added explanatory comment block at `aegis-verify-attestation.yml:169-184` documenting historical typo.
- **F4 HIGH/C3**: `e3-workflow-selftest.yml`'s assert-tampered-digest + assert-expired must declare `if: ${{ !cancelled() }}` to run when the upstream reusable-workflow `verify` job FAILS. GitHub Actions does NOT support `continue-on-error: true` on reusable-workflow `uses:` invocations (job-level), AND the composite Action's `verify_action.py` exits 1 on `valid=false` — meaning the reusable workflow's `verify` job propagates FAIL to its caller. Without the `if:` clause, the assert jobs SKIP by default, masking whether the AEGIS-taxonomy error_class actually surfaced.
- **F5 MEDIUM/C3**: `e3-workflow-selftest.yml` replay-detection comment blocks (lines 172-205) incorrectly described the seeded `decision_id` as "committed alongside the fixtures" — actually a live runtime value flowed through reusable-workflow outputs. Rewrote both comment blocks to honestly document: (a) decision_id flows via outputs (proves workflow_call indirection works), and (b) the coverage gap that the reusable-workflow `AttestationReplayDetected` surface is verified INDIRECTLY via the composite Action's same code path.
- **F8 LOW/C3 (fixed)**: Dead `slsa.dev` BYOB-pattern URL (the prior plan-time citation returned HTTP 404 per WebFetch 2026-05-13) replaced with the valid canonical `github.com/slsa-framework/slsa-github-generator/blob/main/BYOB.md` in both REUSABLE-WORKFLOW.md (line 315) and CHANGELOG.md [1.2.0] §"Upstream references". Regression-guarded by `TestSlsaUrlF8Regression` (2 tests).
- **F10 LOW/C2 (fixed)**: REUSABLE-WORKFLOW.md "When to use" decision-matrix runs-on row corrected — caller DOES control `runs-on` via the `runs-on` input; prior row incorrectly said "NO".
- **F11 LOW/C2 (fixed)**: REUSABLE-WORKFLOW.md "Industry precedent" cell relabeled "slsa-installer" → "slsa-verifier/actions/installer" (the actual repo path).
- **F13 INFO/C3 (fixed)**: `docs/roadmap.md` Sprint 6/F1 row clarified to name the reusable workflow surface (E3) as the dogfood target.

**Phase 2 deferred LOWs**:
- F9+F12 LOW/C3 emoji-width ASCII drift in 3 dep-graph boxes — documented in `.quality-gate/accepted-findings.jsonl` as `wontfix`. Cosmetic only; no functional/CI impact.

**Phase 2 pre-flagged findings verdict**:
- PRE-A CONFIRMED → F1+F2 fix
- PRE-B REFUTED — `actions/upload-artifact@ea165f8d…` + `actions/download-artifact@d3f86a10…` are valid v4.6.2 + v4.3.0 SHAs (verified via GitHub releases page)
- PRE-C CONFIRMED → F8 fix

**Phase 3 /ultrathink 10-probe adversarial audit — 1 finding remediated** (commit `5d2c0ed`):

- **Probe 3 LOW/C3**: `test_assert_jobs_for_expected_failure_run_even_on_upstream_fail` accepted `success()` in its `allowed_patterns` set — a future regression `if: ${{ !cancelled() }}` → `if: ${{ success() }}` (which would silently re-introduce the F4 bug) would still pass the test. Tightened to exclude `success()` + added defensive negative assertion.
- Probes 1, 2, 4-10: NO findings (10-probe coverage on context-variable correctness, `!cancelled()` semantics, edge cases, E2 regression risk, GHES out-of-scope, input mapping, forward-compat informational, run-summary tradeoff informational, README link integrity).

**Post-remediation gate state**:
- pytest: **26/26 PASS** (20 baseline + 6 new regression)
- error-class parity: **15-vs-15 PASS** (no taxonomy change)
- fingerprint parity: **2-vs-2 PASS** (no key change)
- YAML parse: 2/2 NEW workflows + 9 existing = 11/11 OK
- yamllint -d relaxed: exit 0 (line-length warnings only)
- 0 new TODO/FIXME; 0 new external dependencies; 0 new credentials; 0 production runtime impact

**Phase 4 /review** (senior-eng pre-merge audit, 8 sections): APPROVE for merge.
**Phase 5 /ai-code-review** (pre+post-flight 11-check anti-pattern audit): 0 issues across all checks.
**Phase 6 full validation** (7 sub-checks mirroring CI gates): ALL GREEN.

### Upstream references

- Cosmic-flute plan §35: `~/.claude/plans/let-s-plan-this-cosmic-flute.md` (Ultraplan-approved 2026-05-14 session `01FqgCT4cEBWxjvaPmH9Ck5Q`)
- Cosmic-flute §34: Sprint 5/E2 execution plan (composite Action this workflow wraps)
- Cosmic-flute §34.17: Sprint 5/E2 ship capture + sole-keyholder merge pattern
- ADR-001 §Decision: trust model + SHA-pinning + consumer-owned replay-detection responsibility
- Upstream ADR-011: hybrid envelope spec + verifier-statelessness
- SLSA-framework BYOB pattern: <https://github.com/slsa-framework/slsa-github-generator/blob/main/BYOB.md>

---

## [1.1.0] — 2026-05-13

**Sprint 5/E2 ship** — closes cosmic-flute task #119 (consumer-owned replay-detection contract) + task #28 (composite GitHub Action).

### Added

- **`policy/verifier-policy-v1.yaml replay_detection:` block** (companion `policy_version` bump 2.0.0 → 2.1.0). Documents the consumer-owned replay-detection contract: AEGIS verifier (server-side `/attestations/verify` + SDK offline `verify_attestation_locally`) is STATELESS by design per upstream ADR-011 §"Verifier statelessness"; replay detection is consumer-owned. The block declares: policy (`consumer-owned`); primary mechanism (`decision-id-uniqueness`); secondary mechanism (`nonce-uniqueness` for high/critical); 3 recommended consumer stores; composite-action support metadata (the `replay-store-path` input + emit-`AttestationReplayDetected`-on-duplicate behavior).
- **ADR-001 §"Consumer-owned replay-detection responsibility"** subsection under §Decision. Explains the responsibility split + implementation guidance + how the composite Action's `replay-store-path` input provides built-in append-only-file support.
- **`actions/verify-aegis-attestation/action.yml`** (composite GitHub Action). Inputs: `envelope`, `expected-digest`, `expected-environment`, optional `policy-version-expected` / `replay-store-path` / `python-version` / `aegis-sdk-version` / `aegis-sdk-git-ref`. Outputs: 9 fields including `valid`, `error-class` (AEGIS taxonomy), `decision-id`, `nonce`, `replay-checked`. Composite steps: setup-python → install `aegis-sdk[verify]` → run `scripts/verify_action.py`. Consumers pin by immutable commit SHA: `uses: undercurrentai/aegis-policy/actions/verify-aegis-attestation@<sha>`.
- **`actions/verify-aegis-attestation/README.md`** — consumer-facing docs: TL;DR, full inputs/outputs tables, installation source (Git ref fallback while task #59 PyPI publish pending), 19-string error_class taxonomy table (15 verifier-layer + 4 composite-action-layer), replay-detection mechanics, minimal + risk-class-gating examples, SHA-pinning expectations, versioning.
- **`scripts/verify_action.py`** — Python entry-point (~440 LOC). Pins keys from `keys/`, parses policy, runs runtime fingerprint cross-check (DiD: catches key-vs-policy drift across cached runner action checkouts), parses envelope (inline or `@path`), calls `aegis-sdk.verify_attestation_locally`, extracts predicate for output + enforces `policy_version` strict-equal (per upstream ADR-011 N3), optionally consults consumer-owned replay store (append-only file mechanism). Supports `AEGIS_KEYS_DIR_OVERRIDE` + `AEGIS_POLICY_PATH_OVERRIDE` env vars for self-test fixture isolation.
- **`tests/fixtures/generate_fixtures.py`** — one-shot offline generator (idempotent re-runnable). Produces ephemeral Ed25519 + ML-DSA-65 keypair (NOT production keys) + test-policy with matching fingerprints + 3 envelope fixtures (valid-preview / tampered-digest / expired) + manifest.json with digests + decision_ids. Mirrors aegis-sdk wire format byte-for-byte (RFC 8785 canonical JSON + DSSE PAE + uniform `H(CONTEXT_STRING ‖ PAE) → ML-DSA-65/Ed25519` per upstream ADR-012).
- **`tests/test_verify_action.py`** — 12 unit tests (TestEndToEnd × 4 happy/tampered/expired/replay + TestKeyFingerprint + TestPolicyVersion + TestEnvelopeShape × 2 + TestEnvelopeParsing × 2 + TestOutputEmission + TestWarningOnNoReplayStore). Subprocess-isolated; exercise scripts/verify_action.py end-to-end against committed fixtures. 12/12 PASS locally on 2026-05-13.
- **`.github/workflows/e2-action-selftest.yml`** — `workflow_dispatch:` self-test workflow with 5 jobs (unit-tests + 4 composite-action invocations: happy / tampered-digest / expired / replay-detected). Activation path post-task-#59 PyPI publish documented in workflow header.

### Changed

- **`policy/verifier-policy-v1.yaml`**: `policy_version` 2.0.0 → 2.1.0 (MINOR — additive `replay_detection:` block only; `fail_closed_on:` unchanged at 15 entries). Existing v2.0.0 consumers continue to function; replay-detection support is opt-in via `replay-store-path` input on the new composite action.
- **`policy/CHANGELOG.md [2.1.0]`** — additive contract field documented; migration steps for consumers wanting replay detection.
- **`policy/PROVENANCE.md`** — `replay_detection` row added; v2.1.0 vendoring source row (SDK unchanged at `aegis-governance@dc9c9df`).
- **`docs/roadmap.md`**: Sprint 5/E1.5 row → ✅ shipped 2026-05-12 (per cosmic-flute §32); Sprint 5/E2 row → 🟡 in-progress (this PR) with corrected scope description (cosign-signed kit container release was incorrectly listed under E2 — that's Phase 2 ecosystem-compat per cosmic-flute §34.13 OOS).

### Notes

- **4 composite-action-layer error_classes** (`AttestationKeyFingerprintMismatch`, `AttestationEnvelopeShapeInvalid`, `AttestationPolicyVersionMismatch`, `AttestationReplayDetected`) are INTENTIONALLY OMITTED from `policy/verifier-policy-v1.yaml fail_closed_on`. They live in the action README (`actions/verify-aegis-attestation/README.md §Error classes`) since they're enforced at the action layer, not the verifier layer. This preserves the SDK ↔ policy parity invariant (`error-class-parity.yml` CI gate stays GREEN at 15 vs 15 entries without requiring an SDK re-vendor).
- **Self-test workflow `workflow_dispatch:`-only at v1.1.0**. Adds `pull_request:` trigger once task #59 (aegis-sdk PyPI publish) lands OR a `AEGIS_SDK_FETCH_TOKEN` secret is configured in repo settings.
- **Sprint 5/E3 reusable workflow (task #29)** deferred — wraps this composite for `workflow_call:` consumers.

### Quality-gate hardening (Phase 2 + Phase 3 remediations)

Pre-ship `/quality-gate` 9-phase exhaustive run remediated 11 findings + added 8 regression tests:

- **`tests/conftest.py`** (NEW): session-scoped `autouse` fixture that runs `tests/fixtures/generate_fixtures.py` on cold checkouts if `manifest.json` is missing. Closes Phase 2 Agent 1 F2 (pytest collection failure on fresh-clone state).
- **`tests/fixtures/generate_fixtures.py`**: fixture envelope now emits `payloadType` (camelCase) per in-toto + DSSE v1 JSON wire format. Closes Phase 2 Agent 1 F1 — the prior `payload_type` (snake_case) was silently accepted by SDK's default-fallback in `DSSEEnvelope.from_response`, masking the wire-format contract.
- **`scripts/verify_action.py`**:
  - `AEGIS_INTERNAL_FIXTURE_MODE=1` sentinel gates `AEGIS_KEYS_DIR_OVERRIDE` + `AEGIS_POLICY_PATH_OVERRIDE` env vars. Closes Phase 3 ultrathink probe 4 — defense-in-depth against compromised prior steps in consumer workflows that could `echo "AEGIS_KEYS_DIR_OVERRIDE=./malicious" >> $GITHUB_ENV`. Production consumers NEVER set the sentinel; overrides silently ignored.
  - Replay-store I/O failure now emits `replay-checked=false` (was `true`). Closes Phase 2 Agent 1 F4 — the prior `true` would falsely tell consumers the audit trail is durable when an append failed.
  - `AEGIS_EXPECTED_DIGEST` format-validated (64-char lowercase hex). Closes Phase 2 Agent 1 F7.
  - Envelope-parse except adds `UnicodeDecodeError` (alongside JSON/FileNotFound/OS). Closes Phase 2 Agent 1 F6 — binary `@path` no longer crashes the action.
- **`tests/test_verify_action.py`**:
  - Subprocess env-strip extended to `GITHUB_*` (was `AEGIS_*` only). Closes Phase 2 Agent 1 F5 — parent process's stale `GITHUB_OUTPUT` / `GITHUB_WORKSPACE` no longer leak.
  - Cycle 2 hardening: `test_subprocess_isolates_inherited_github_output` now calls `_run_verify(github_output_path=None)` so the strip is the only defense — proven by empirical sed-revert smoke that the test fails with `KeyError 'valid'` if the strip is removed.
  - 8 cumulative regression tests added (`TestPhase2Regression` × 7 + sentinel gate × 1) — `test_fixture_envelope_uses_camelcase_payloadType_key`, `test_malformed_expected_digest_rejected`, `test_short_expected_digest_rejected`, `test_binary_at_path_envelope_input_rejected`, `test_subprocess_isolates_inherited_github_output`, `test_replay_store_write_failure_marks_replay_unchecked`, `test_override_env_vars_ignored_without_fixture_mode_sentinel`.
- **`actions/verify-aegis-attestation/README.md`**:
  - Worked example replaced `${{ steps.X.outputs.Y }}` interpolation in `run:` block with `env:` propagation pattern per [GitHub Security Lab](https://securitylab.github.com/resources/github-actions-untrusted-input) + CodeQL `actions-code-injection-medium`. Closes Phase 2 Agent 2 F1 (the prior snippet taught consumers a known-bad pattern).
  - Replay-detection section adds 4 sub-sections: workspace-relative AND absolute path support; Concurrency caveat (TOCTOU under matrix builds / `workflow_call` fan-out); Retention guidance (consumer GCs); Store-write failure semantics. Closes Phase 2 Agent 2 F3.
  - `actions/checkout@v6` example bumped to SHA-pin `de0fac2e…` (was tag-pin contradicting our own SHA-pinning guidance). Closes Phase 2 Agent 2 F6.
  - SHA-pinning section adds "Transitive pins" bullet noting `actions/setup-python@a309ff8b…` (v6) inner pin. Closes Phase 2 Agent 2 F5.
- **`docs/architecture/adr/ADR-001-repo-trust-model.md` §"Consumer-owned replay-detection responsibility"**: implementation guidance reframed from mutually-exclusive (`For high/critical: nonce; For low/medium: decision_id`) to additive (`Primary mechanism (all classes): decision_id-uniqueness; Additional mechanism for high/critical: nonce on top`). Matches `policy/verifier-policy-v1.yaml replay_detection.mechanism_primary` + `mechanism_secondary`. Closes Phase 2 Agent 2 F2.
- **`.github/workflows/e2-action-selftest.yml`**: removed `needs: unit-tests` from all 4 action-invocation jobs. They now run in parallel. Closes Phase 2 Agent 2 F4. Each job's env block adds `AEGIS_INTERNAL_FIXTURE_MODE: "1"` sentinel for the Phase 3 P4 fix.

Total: 11 findings remediated (Phase 2 cycle 1 × 9 + Phase 2 cycle 2 × 1 + Phase 3 ultrathink × 1) + 4 LOWs (UnicodeDecodeError, digest-format-validation, transitive pin docs, checkout SHA-pin); 8 regression tests added cumulative; final pytest 20/20 PASS, error-class parity 15-vs-15, fingerprint parity 2-vs-2, YAML parse 10/10, yamllint relaxed exit 0, markdownlint-cli2 0 errors.

### Post-merge notes

Admin-squash-merge to main as commit `19a751e` (2026-05-14T02:39:17Z UTC = 2026-05-13 CDT) was blocked by two org-Ruleset `aegis-attestation-required-checks` (id 16294975) rule violations and required mid-flight remediation captured here for the historical audit trail:

- **Required status check name mismatch** — ruleset expected exact-match context `"AEGIS Shadow Evaluation"`; the workflow job was named `"AEGIS Shadow Evaluation (advisory)"` (carryover Sprint 5/E1 advisory framing). **Fix** (in-flight, squashed into `19a751e` from pre-squash commit `ff0ec71`): renamed the `aegis-shadow-eval.yml` job to drop the `(advisory)` suffix; `continue-on-error: true` retained so transient AEGIS API outages don't permanently block. Sustainable fix; persists in `main` and will satisfy the ruleset for all future PRs.
- **Single-owner structural rule conflict** — `required_approving_review_count: 1` + `require_code_owner_review: true` + `require_last_push_approval: true` are unsatisfiable when one human owns the repo (GitHub disallows author-self-approval; `require_last_push_approval` requires a non-pusher to approve). **Fix** (transient): snapshot ruleset state → add `OrganizationAdmin` to `bypass_actors` for ~30 seconds → `gh pr merge --admin --squash` → restore `bypass_actors: []` immediately. Operating pattern documented in cosmic-flute §34.17.2 for future single-owner aegis-policy PRs until the team grows beyond one engineer per ADR-001's documented growth path. The org-Ruleset's `bypass_actors=[]` commitment per cosmic-flute §17 Critical 3 is preserved as the steady-state invariant; the bypass cycle creates a full audit trail in GitHub's Activity log.

### Upstream references

- Cosmic-flute plan §34: `~/.claude/plans/let-s-plan-this-cosmic-flute.md`
- ADR-001 §Decision §"Consumer-owned replay-detection responsibility" (this repo, updated in this PR)
- Upstream ADR-011 §"Verifier statelessness": `aegis-governance@dc9c9df:docs/architecture/adr/ADR-011-artifact-bound-aegis-attestations.md`
- Vendored SDK source: `aegis-governance@dc9c9df:aegis-sdk/src/aegis/_verify_local.py` (unchanged from v2.0.0 — `replay_detection:` is a contract-only addition; no SDK code change)

---

## [1.0.0] — 2026-05-10

Sprint 5/E1.5 Phase 5 ship. Repo graduates from `0.x` bootstrap series to `1.x` stable series — the canonical verifier-policy + trust roots are now production-derived (not placeholder).

### Added

- **Real public-key bytes**: `keys/ed25519-public.pem` (113B PEM-wrapped 32B raw) + `keys/mldsa65-public.bin` (1952B raw) — KMS-derived from `undercurrent-production/us-central1/aegis-attestation` keyring (Phase 1 ceremony per cosmic-flute §28.17; SOFTWARE protection per [ADR-002](docs/architecture/adr/ADR-002-key-ceremony-2026-05-10.md))
- **`scripts/check_fingerprints.py`** + **`.github/workflows/fingerprint-parity.yml`**: bytes ↔ fingerprints invariant CI gate. Closes the single-char-typo failure mode for `policy/verifier-policy-v1.yaml required_keyids`.
- **`scripts/extract_mldsa65_raw.py`**: ASN.1 DER parsing utility for KMS-emitted ML-DSA-65 X.509 SubjectPublicKeyInfo PEM → raw 1952B (workaround for Python `cryptography` library not yet recognizing OID `2.16.840.1.101.3.4.3.18`)
- **ADR-002** (`docs/architecture/adr/ADR-002-key-ceremony-2026-05-10.md`): documents Sprint 5/E1.5 Phase 1 ceremony — AEGIS Stage-2 decision_id `9eae3455-3da1-4f2e-b74b-53b973300a60` ESCALATE → OVERRIDE_APPLIED; SOFTWARE protection acceptance (HSM unavailable for both `EC_SIGN_ED25519` and `PQ_SIGN_ML_DSA_65`); GCP KMS resource provenance; compensating controls
- **ADR-003** (`docs/architecture/adr/ADR-003-ml-dsa-44-to-65-migration.md`): downstream consequence of upstream ADR-012 (algorithm migration on aegis-policy artifacts; v1.0.0 → v2.0.0 BREAKING)

### Changed

- **`policy/verifier-policy-v1.yaml`**: `policy_version` 1.0.0 → 2.0.0 (BREAKING — see `policy/CHANGELOG.md [2.0.0]` for the full delta); algorithm migration ml-dsa-44 → ml-dsa-65; real fingerprints replace `PLACEHOLDER_E1_5_CEREMONY_PENDING`
- **`scripts/_verify_local_vendored.py`**: re-vendored from `aegis-governance@7e422b2` (Sprint 5/E1.5 Phase 4 + audit-pass PR #171), replacing the pre-migration vendoring from `aegis-governance@37f8608`
- **`docs/key-rotation-runbook.md`**: replaced E1.5 TODOs with full KMS-only rotation procedure (steady-state + emergency-compromise paths)
- **`keys/README.md`**: replaced "ceremony pending" placeholder text with file references, real fingerprints, and pinning model documentation
- **`policy/PROVENANCE.md`**: vendored-source SHA bumps (schema `a5c0bfd` → `7e422b2`; SDK `37f8608` → `7e422b2`); ADR-012 source-of-truth attribution
- **`docs/roadmap.md`**: Sprint 5/E1.5 row 🟢 in-progress (Phases 1-5 shipped via this PR; Phases 6-8 downstream)

### Notes

- Composite GitHub Action `verify-aegis-attestation` still deferred to Sprint 5/E2.
- Reusable workflow `aegis-verify-attestation.yml` still deferred to Sprint 5/E3.
- Org-level GitHub Ruleset enforcement deferred to Sprint 5/E1.5 Phase 7 (admin operation; post this PR merge).
- Production Cloud Run redeploy (Sprint 5/E1.5 Phase 6) is the downstream consumer of this PR + the merged aegis-governance@`7e422b2`.

### Upstream references

- Cosmic-flute plan §28 + §30: `~/.claude/plans/let-s-plan-this-cosmic-flute.md`
- Upstream ADR-011 (artifact-bound attestations) + ADR-012 (algorithm migration + uniform prefix-hash-and-sign): `aegis-governance@7e422b2`
- Vendored SDK source: `aegis-governance@7e422b2:aegis-sdk/src/aegis/_verify_local.py`

---

## [0.1.0] — 2026-05-09

### Added

- **Sprint 5/E1 repo bootstrap**: governance scaffolding (CODEOWNERS, NIST 800-53r5 PR template, dependabot, lint/AEGIS-shadow-eval/error-class-parity workflows), contract vendoring (predicate schema v1 + interface-contract attestation: section, vendored verbatim from `aegis-governance@a5c0bfd`), canonical verifier-policy artifact (`policy/verifier-policy-v1.yaml` v1.0.0), trust-model ADR-001, key-rotation runbook stub, roadmap.
- **Apache-2.0 LICENSE** (matches aegis-sdk precedent; intentional split from BSL-1.1 server-side per cosmic-flute §26.15 C).
- **Error-class parity CI gate** (`scripts/check_error_class_parity.py` + `.github/workflows/error-class-parity.yml`): cross-checks `policy/verifier-policy-v1.yaml fail_closed_on` against the latest `aegis-governance[verify]>=0.6.1` SDK's emitted error_class set on every PR. Closes the manual audit gap from cosmic-flute §26.11 step 4.

### Notes

- Real Ed25519 + ML-DSA-44 public keys deferred to Sprint 5/E1.5 ceremony (separate plan, AEGIS-self-tune-class gate). `keys/` contains documentation only at v0.1.0.
- Composite GitHub Action `verify-aegis-attestation` deferred to Sprint 5/E2.
- Reusable workflow `aegis-verify-attestation.yml` deferred to Sprint 5/E3.
- Org-level GitHub Ruleset enforcement deferred to Sprint 5/E1.5.

### Upstream references

- Cosmic-flute plan §26: `~/.claude/plans/let-s-plan-this-cosmic-flute.md`
- Ultraplan refinement session `01G2i7fu6w8cdk8Xw9T7TZrE` (2026-05-09)
- ADR-011: https://github.com/undercurrentai/aegis-governance/blob/main/docs/architecture/adr/ADR-011-artifact-bound-aegis-attestations.md
- Vendored schema source: `aegis-governance@a5c0bfd6379f85d506ff47656aa4ee4ec5eb56a4`
