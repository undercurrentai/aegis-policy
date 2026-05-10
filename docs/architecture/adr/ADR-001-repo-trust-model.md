# ADR-001: Repo Trust Model

## Status

**Proposed** | 2026-05-09 (flips to **Accepted** on bootstrap PR #1 admin-merge to main)

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
