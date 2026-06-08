# AEGIS Policy

Verifier kit + canonical trust roots for AEGIS cryptographic attestations (per [ADR-011](https://github.com/undercurrentai/aegis-governance/blob/main/docs/architecture/adr/ADR-011-artifact-bound-aegis-attestations.md)).

## What's here

| Path | Purpose |
|---|---|
| `schema/` | Vendored predicate schema v1 + interface-contract `attestation:` section, sourced verbatim from `aegis-governance@a5c0bfd`. Self-contained — consumers don't need to clone the parent repo. |
| `policy/` | **Canonical verifier policy artifact** (`verifier-policy-v1.yaml`). Lists required algorithms, required keyids (real SHA-256 fingerprints since Sprint 5/E1.5), required context bindings, fail-closed conditions, TTL per risk class, nonce policy, policy_version compatibility. Consumers pin this file by **immutable SHA**, never by `@main`. |
| `keys/` | Canonical Ed25519 + ML-DSA-65 public keys for hybrid PQ-ready verification. Real KMS-derived keys committed at Sprint 5/E1.5 (2026-05-12); `policy_version` `v2.0.0` per the ML-DSA-44 → ML-DSA-65 migration (upstream ADR-012). |
| `docs/` | Trust-model ADR-001, governance summary, key-rotation runbook stub, roadmap. |
| `scripts/` | Maintenance: error-class parity check (CI gate). |
| `.github/workflows/` | Lint + AEGIS shadow-eval (advisory) + error-class parity (gating). |

Shipped since the early roadmap: real public keys (Sprint 5/E1.5), the composite Action `verify-aegis-attestation` (E2), the reusable workflow `aegis-verify-attestation.yml` (E3), dogfood integration (Sprint 6/F1 aegis-deploy.yml + F2 openclaw blue-green Phase 1), and org-level GitHub Ruleset enforcement (E1.5 attestation ruleset + §48 enforce ruleset `17101026`, advisory `shadow` mode today).

## What's NOT here (yet)

- **`enforce`-mode flip + full 19-repo rollout** — Sprint 7/G2-G3. The §48 enforce ruleset runs in `shadow` on the source repos today; the consumer rollout + shadow→enforce flip are pending the calibration window.
- **Cosign-signed kit container release** (`ghcr.io/undercurrentai/aegis-policy`) — deferred to Phase 2 ecosystem-compat per cosmic-flute §34.13 OOS.

See [`docs/roadmap.md`](docs/roadmap.md).

## Trust model

This repo is the **single source-of-truth** for AEGIS attestation verification across the 20-repo Undercurrent portfolio. Per cosmic-flute §17 Critical 3 + ADR-011 §Negative §6:

- **CODEOWNERS-protected** on `keys/`, `schema/`, `policy/`, `.github/` (see `.github/CODEOWNERS`)
- **SHA-pinning required** in consumer repos (never `@main`)
- **Org-level GitHub Ruleset** enforces required status checks (Sprint 5/E1.5)
- **Distinct AEGIS instance evaluating policy changes** (Sprint 5/E1.5)

See [`docs/architecture/adr/ADR-001-repo-trust-model.md`](docs/architecture/adr/ADR-001-repo-trust-model.md) for the full threat model + mitigations.

## License

**Apache-2.0** — this is a **client-side verifier kit**. Client libraries ship permissive per industry convention (sigstore, slsa-verifier, in-toto, datadog-agent, vault-action all Apache-2.0). The parent `aegis-governance` SaaS server stays **BSL-1.1** (revenue protection); the verifier kit is intrinsically commodity (Ed25519 + ML-DSA-65 + RFC 8785 + DSSE are open standards, derivable in ~250 LOC from the publicly-vendored schema). See cosmic-flute §26.15 C for the full industry-pattern rationale.

## Reporting security issues

Email `security@undercurrentholdings.com` or use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability).

## Status

`v1.2.7` — Sprint 7/G1 in progress: §48 enforce substrate (relocated to this repo, `shadow` mode, org-Ruleset `17101026`), §51 cross-repo `resolve_callee` fix (v1.2.6), and §44 Phase 2 (v1.2.7) which retires the sole-keyholder bypass cycle for routine PRs (3-AI consensus auto-approve via `@aegis-auto-reviewer`). aegis-governance v1.2.7 in production since 2026-05-21. See `CHANGELOG.md` for the cumulative ship cycle (E1 → E1.5 → E2 → E3 → sub-phase 3a → QG-§37.18 → sub-phase 4 v1.2.6 → §38 v1.2.7 → §48 → §51 v1.2.6 → §44 Phase 2 v1.2.7).
