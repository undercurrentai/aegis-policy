# ADR-001: Repo Trust Model

## Status

**Accepted** | 2026-05-09 (bootstrap PR #1 admin-squash-merged to main as commit `9c25b38`)

## Context

Per cosmic-flute §17 Critical 3 + ADR-011 §Negative §6, the AEGIS attestation system has a structural risk: the verifier kit + canonical policy artifact + canonical public keys form a high-leverage trust concentration. A compromise of the kit's source repo, its CI pipeline, or the policy artifact would affect all 20 portfolio consumer repos simultaneously.

The mitigation must address two distinct attack surfaces:

1. **Direct compromise of the verifier-kit repo**: an attacker who can write to `keys/`, `policy/`, `schema/`, or `.github/workflows/` can undermine verification across the entire portfolio.
2. **Indirect compromise via consumer-repo PR-driven changes**: an attacker with PR access to a consumer repo could attempt to relax the consumer's pinned aegis-policy SHA, rolling back to a permissive policy.

ADR-011 references this repo (`undercurrentai/aegis-policy`) for verifier-policy distribution but defers the trust-model design to Sprint 5/E1.

## Decision Drivers

| Driver | Weight | Notes |
|---|---|---|
| Tamper-evidence on the verifier-kit repo itself | High | Single owner today; CODEOWNERS-protected paths; org-ruleset bypass-actor empty |
| Tamper-evidence on consumer-repo pin updates | High | SHA-pinning required (never `@main`); consumer-repo CODEOWNERS gates pin bumps |
| Auditability for external reviewers | Medium | Public repo; every change visible in git history; signed commits encouraged |
| Operational simplicity (sole engineer today) | High | Avoid TUF / threshold-signature ceremonies; Git-versioned trust roots sufficient |
| Industry-pattern alignment | Medium | sigstore, slsa-framework, in-toto all use Git + CODEOWNERS for trust roots before adopting TUF |
| Quarterly-review cadence for TTL + key-rotation | Medium | Documented in policy/verifier-policy-v1.yaml + key-rotation-runbook.md |

## Options Considered

### Option 1: Single repo, CODEOWNERS-protected, SHA-pinned consumers (CHOSEN)

- **Storage**: Git-versioned PEM/raw bytes in `keys/`; YAML in `schema/` + `policy/`
- **Tamper-evidence**: CODEOWNERS-required approval on all paths; org-level GitHub Ruleset (Sprint 5/E1.5) blocks bypass; consumers pin by immutable SHA, never `@main`
- **Pros**: Simple, auditable, uses standard GitHub primitives; matches sigstore/slsa-framework patterns at v1; zero operational burden beyond standard PR review; aligns with single-engineer reality
- **Cons**: Single owner is a stated limitation (documented growth path to 2-of-N team); no threshold-signature defense against owner compromise
- **Mitigations for cons**: When team grows → 2-of-N reviews on strict paths; AEGIS shadow-eval workflow + AEGIS Stage-2 self-eval submitted on every PR adds a non-human gate; `error-class-parity.yml` workflow gates `policy/verifier-policy-v1.yaml fail_closed_on` against SDK source-of-truth, preventing silent removal of fail-closed conditions

### Option 2: Single repo, TUF-backed key distribution

- **Storage**: TUF root metadata + delegated targets metadata + signed key bundles (sigstore root-signing model)
- **Tamper-evidence**: Threshold-signature ceremonies; multiple keyholders required for any rotation; rotates without code changes
- **Pros**: Cryptographically resilient to single-keyholder compromise; standard for high-stakes ecosystems
- **Cons**: Significant operational burden (offline ceremonies, multiple keyholders, mainline + staging metadata pipelines); overkill for v1 (AEGIS attestation keys are stable long-lived service keys, not Fulcio-style short-lived certs that rotate constantly)
- **Verdict**: REJECTED for v1; revisit in Phase-2 ecosystem-compat work if external integrators require it

### Option 3: Two repos (`aegis-policy-keys` private + `aegis-policy-tooling` public)

- **Storage**: Keys in private repo; tooling in public repo; tooling fetches keys at CI time via auth token
- **Pros**: Reduces key-leak surface (private)
- **Cons**: Public-key bytes are public information by design (asymmetric crypto); private storage adds friction without security benefit; consumers in 20 repos would need read-access tokens; auditability suffers
- **Verdict**: REJECTED — public-key privacy is security theater; optimizes the wrong thing

### Option 4: Cosign-keyless (Fulcio + Rekor) verifier kit

- **Storage**: No keys at all; verification uses Fulcio short-lived certs + Rekor transparency log
- **Pros**: No key-management burden
- **Cons**: Requires runtime network access to Fulcio + Rekor (contradicts ADR-011 N5 + Sprint 4/D2 offline-verification design); ecosystem-incompatible with hybrid PQ envelope (sigstore PR #1062 rejects multi-sig DSSE)
- **Verdict**: REJECTED — incompatible with the hybrid PQ design + offline-verification mandate

## Decision

**Chosen: Option 1.** Single repo, CODEOWNERS-protected, SHA-pinned by consumers.

Implementation specifics:

- **CODEOWNERS** (`.github/CODEOWNERS`): default `@ThermoclineLeviathan`; explicit listing of `keys/`, `schema/`, `policy/`, `.github/`, `.github/workflows/`, `docs/architecture/`, `scripts/` for visibility. Single owner today + documented growth-path to `@undercurrentai/security-reviewers` 2-of-N team.
- **Org-level GitHub Ruleset** (Sprint 5/E1.5 admin op): `aegis-policy-critical-checks` requires `lint.yml` + `error-class-parity.yml` + CODEOWNERS approval before merge to `main`; bypass actors empty (admins included).
- **Consumer SHA-pinning**: per-consumer-repo workflows reference `undercurrentai/aegis-policy@<commit-sha>`, never `@main` or `@v1.0.0` (tags are mutable in some contexts).
- **AEGIS Stage-2 shadow-eval**: every PR runs `aegis-shadow-eval.yml` advisory workflow that calls `aegis_evaluate_proposal`; decision_id captured in PR body; non-blocking but creates audit trail.
- **Error-class parity gate**: `error-class-parity.yml` workflow auto-checks `policy/verifier-policy-v1.yaml fail_closed_on` against the latest published `aegis-governance[verify]` SDK's emitted error_class set on every PR. Prevents silent drift between SDK and policy.
- **Key rotation**: Git-versioned PEM/raw bytes; PR-gated rotation per `docs/key-rotation-runbook.md`; full ceremony defined in Sprint 5/E1.5.
- **Distinct AEGIS instance evaluating policy changes**: deferred to Sprint 5/E1.5 (would require provisioning a separate AEGIS API key with restricted scope; out of E1 scope).

### Consumer-owned replay-detection responsibility

Added 2026-05-13 in Sprint 5/E2 Phase A (task #119; design dependency surfaced by post-ship /quality-gate Phase 3 ultrathink U1 on v1.2.4).

AEGIS attestations bind to immutable build provenance and are cryptographically verifiable in isolation (per upstream ADR-011 §Decision). However, the verifier — both server-side `/attestations/verify` and SDK offline `verify_attestation_locally` — is **stateless by design**. The verifier does NOT track whether a given attestation envelope has been seen before.

This is intentional: the verifier-stateless trust model (upstream ADR-011 §"Verifier statelessness") keeps the verification surface minimal, deterministic, and free of consumer-state dependencies. It also enables the same envelope to be verified in multiple downstream contexts without coordination.

**Consequence**: replay detection is the consumer's responsibility. A consumer that accepts a verified envelope as authoritative MUST also check that the envelope's `decision_id` (or `nonce`, for high/critical risk_class) has not been seen before in the consumer's own authority domain.

**Implementation guidance**:

- **Primary mechanism (all risk classes)**: `decision_id`-uniqueness check. Every issued attestation carries a unique `decision_id` (UUID); consumers maintain a store of seen `decision_id` values and reject duplicates.
- **Additional mechanism for `high`/`critical` risk_class**: `nonce`-uniqueness check on top of `decision_id` (defense-in-depth; the predicate's `nonce` field is always present for high/critical per `policy/verifier-policy-v1.yaml nonce_required_for_risk_classes`). Consumers requiring nonce-aware behavior hash `decision_id + nonce` into the store entry.
- **Store options**: append-only file, DB unique constraint, Redis SETNX with TTL aligned to `envelope.predicate.governance.expires_at`, or equivalent.

This matches the `policy/verifier-policy-v1.yaml replay_detection.mechanism_primary` (all classes) + `mechanism_secondary` (high/critical only) contract — additive, not mutually-exclusive.

**Built-in support via Sprint 5/E2 composite Action**: the `undercurrentai/aegis-policy/actions/verify-aegis-attestation@<sha>` action (Sprint 5/E2) accepts an optional `replay-store-path` input that implements the append-only-file mechanism for consumers without their own store. When the input is unset, the action emits a `::warning::` in the step summary and still emits `valid: true` on cryptographic success — leaving the consumer's CI workflow to decide whether to gate on replay externally.

The composite action emits `AttestationReplayDetected` from the action layer (NOT the verifier layer) when a duplicate `decision_id` is found in the consumer-owned store. This new error_class is documented in the action's README and is INTENTIONALLY OMITTED from `policy/verifier-policy-v1.yaml fail_closed_on` — preserving the SDK ↔ policy parity invariant (15 vs 15 entries) without requiring an SDK re-vendor.

See `policy/verifier-policy-v1.yaml replay_detection` for the machine-readable contract.

### Cross-repo workflow_call self-checkout: callee-context vs caller-context

Added 2026-05-19 in Sprint 6/F1 sub-phase 3a (task #173; root-cause discovery from sub-phase 3 dry-run RUN 25980426234, 2026-05-17). See cosmic-flute §37.17 (root-cause analysis) + §37.18 (execution plan).

When a reusable workflow defined in this repo is invoked via `uses: undercurrentai/aegis-policy/.github/workflows/<file>@<sha>` from a CALLER repository under `workflow_call` semantics, the GitHub Actions `github` context becomes associated with the CALLER, not the callee (this repo). Specifically:

- `github.workflow_sha` resolves to the CALLER's commit SHA (NOT the reusable workflow's pinned SHA)
- `github.workflow_ref` resolves to the CALLER's workflow ref (NOT this reusable workflow's ref)
- `github.repository` is the CALLER's repository
- `GITHUB_WORKFLOW_REF` env var is also CALLER-scoped (per github/gh-aw issue #24949)

This contradicts both older Stack Overflow guidance AND an earlier reading of the GitHub Docs Contexts reference. Per GitHub Actions runtime debug output (github/gh-aw issue #24918, filed 2026-04-06) and the Microsoft `gh-aw` maintenance fixes (PRs #24200 / #24433 / #24974, all 2026-04): `github.workflow_*` is caller-scoped in `workflow_call`. Reusable workflows MUST use the `job` context properties for self-referential values:

- `job.workflow_repository` — owner/repo of THIS reusable workflow's source repo
- `job.workflow_sha` — commit SHA of THIS reusable workflow's source file

For GitHub Enterprise Server (where `job.workflow_*` is unavailable per docs.github.com), the canonical fallback is the GitHub API's `referenced_workflows` array returned by `GET /repos/{owner}/{repo}/actions/runs/{run_id}` — find the entry matching the reusable workflow's filename and use its `sha` (preferring SHA over `ref` for immutability per gh-aw PR #24974 best practice).

This repo's reusable workflows MUST use the `job.workflow_*` + API fallback pattern documented in `.github/workflows/aegis-verify-attestation.yml`. The regression test `tests/test_workflow_invariants.py::TestCrossRepoCheckoutPattern` guards against future regressions to the `github.workflow_*` pattern.

**Production discovery context**: this bug was caught by cosmic-flute §37 Sprint 6/F1 sub-phase 3 dry-run (aegis-governance RUN 25980426234, 2026-05-17). All 4 prior jobs in the deploy pipeline passed; the local Tier-4e canonical proof with real pinned keys also passed (the trust spine itself was intact). Only the verifier-kit's self-checkout step failed. Validates §17 Critical 3 dogfood-before-rollout pattern — the bug would have shipped to all 19 Sprint 7/G2-G3 consumers if not caught by aegis-governance dogfood.

**Lesson learned**: aegis-policy's `e3-workflow-selftest.yml` (Sprint 5/E3) invokes the reusable workflow via `workflow_dispatch:` from WITHIN aegis-policy — a fundamentally different code path because `github.workflow_*` happens to resolve to aegis-policy's own values in that local invocation. True cross-repo regression coverage requires either (a) a dedicated test consumer repo, or (b) feature-branch validation on a real consumer like aegis-governance (the chosen path per §37.18.11 L2 + §37.18.7).

**References**:
- GitHub Docs: Contexts reference §job (https://docs.github.com/en/actions/reference/workflows-and-actions/contexts)
- github/gh-aw issue #24918 (the runtime debug output proof, filed 2026-04-06)
- github/gh-aw PRs #24200 + #24433 + #24974 (Microsoft's own fix pattern)
- canonical/get-workflow-version-action (production composite using API fallback, since 2024)
- cosmic-flute §37.17 (root-cause analysis from sub-phase 3 dry-run, 2026-05-17)
- cosmic-flute §37.18 (this hotfix execution plan, 2026-05-18→19)

## Consequences

### Positive

- Operational simplicity: standard GitHub primitives + CODEOWNERS + org rulesets; no custom ceremony tooling at v1
- Auditability: every change visible in git history; PRs run AEGIS shadow-eval + parity check
- Industry-pattern alignment: matches sigstore/slsa-framework v1 trust-root model (TUF was added later, after operational experience justified it)
- Aligns with single-engineer reality without pretending to multi-reviewer governance that doesn't exist yet
- Auto-conversion to fully-open Apache-2.0 protocol (no key rotation needed for license bump in 4 years)

### Negative

- **Single owner today** is a structural risk; mitigated by documented growth path + AEGIS shadow-eval + parity gate, but not eliminated
- **No threshold-signature defense** against owner compromise; mitigated by org-ruleset bypass-actor-empty + GitHub's built-in audit log
- **Public-key bytes will be in git history forever** — acceptable since they're public by design, but means no "delete a leaked private key from history" remediation if leakage ever happens (the private key would never be in this repo; only the public key)
- **Trust concentration unchanged from ADR-011 §Negative §6** — this ADR mitigates but does not eliminate; future Phase-2 work could add TUF if external integrators require it

### Neutral

- 20-repo portfolio (was 19 before this repo's creation per CLAUDE.md count)
- Apache-2.0 license is permissive — anyone can fork the kit, but cannot generate valid AEGIS attestations without the private keys (which never leave GCP KMS in production)

## Implementation Plan

See cosmic-flute §26: `~/.claude/plans/let-s-plan-this-cosmic-flute.md`. Sequence:

1. Sprint 5/E1 (this PR): repo bootstrap + governance scaffolding + contract vendoring + canonical verifier-policy `v1.0.0` (placeholder keys)
2. Sprint 5/E1.5 (next): real key generation + GCP KMS wiring + org-ruleset config + distinct AEGIS instance (admin op)
3. Sprint 5/E2: composite GitHub Action consuming this repo's policy + keys
4. Sprint 5/E3: reusable workflow consuming the E2 action
5. Sprint 6/F1+F2: dogfood (aegis-governance + openclaw-operator-os become the first consumers)
6. Sprint 7/G1+G2+G3: org-Ruleset rollout + 20-repo rollout

## References

- Cosmic-flute §17 Critical 3: policy-bootstrap protection
- Cosmic-flute §26: Sprint 5/E1 plan
- ADR-011 §Negative §6: verifier-kit + policy-artifact concentration risk
- ADR-011 §Decision: hybrid Ed25519 + ML-DSA-44 envelope; AND-of-2 enforced by verifier policy
- sigstore/root-signing TUF model: https://github.com/sigstore/root-signing
- slsa-framework verifier-kit pattern: https://github.com/slsa-framework/slsa-verifier
- in-toto attestation envelope spec: https://github.com/in-toto/attestation/blob/main/spec/v1/envelope.md

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-09 | Claude Opus 4.7 (1M context) / Josh Kirby | Initial draft (Status: Accepted on bootstrap PR) |
| 2026-05-13 | Claude Opus 4.7 (1M context) / Josh Kirby | Sprint 5/E2 Phase A: added §Decision subsection "Consumer-owned replay-detection responsibility" (closes task #119; companion to `policy/verifier-policy-v1.yaml replay_detection:` block + v2.1.0 bump). Status stays Accepted; this is an additive clarification, not a new decision. |
| 2026-05-19 | Claude Opus 4.7 (1M context) / Josh Kirby | Sprint 6/F1 sub-phase 3a: added §Decision subsection "Cross-repo workflow_call self-checkout: callee-context vs caller-context" (closes task #173; companion to `.github/workflows/aegis-verify-attestation.yml` defense-in-depth fix + v1.2.1 patch). Documents the canonical 2025/2026 GitHub Actions context-variable semantics for reusable workflows + the production discovery from cosmic-flute §37.17. Status stays Accepted; this is an additive clarification of an implementation-level requirement, not a new architectural decision. |
