# AEGIS Policy

Verifier kit + canonical trust roots for AEGIS cryptographic attestations (per [ADR-011](https://github.com/undercurrentai/aegis-governance/blob/main/docs/architecture/adr/ADR-011-artifact-bound-aegis-attestations.md)).

## What's here

| Path | Purpose |
|---|---|
| `schema/` | Vendored predicate schema v1 + interface-contract `attestation:` section, sourced verbatim from `aegis-governance@a5c0bfd`. Self-contained — consumers don't need to clone the parent repo. |
| `policy/` | **Canonical verifier policy artifact** (`verifier-policy-v1.yaml`). Lists required algorithms, required keyids (placeholders until E1.5), required context bindings, fail-closed conditions, TTL per risk class, nonce policy, policy_version compatibility. Consumers pin this file by **immutable SHA**, never by `@main`. |
| `keys/` | Canonical Ed25519 + ML-DSA-44 public keys for hybrid PQ-ready verification. **Currently placeholder** — real keys land in Sprint 5/E1.5 ceremony. |
| `docs/` | Trust-model ADR-001, governance summary, key-rotation runbook stub, roadmap. |
| `scripts/` | Maintenance: error-class parity check (CI gate). |
| `.github/workflows/` | Lint + AEGIS shadow-eval (advisory) + error-class parity (gating). |

## What's NOT here (yet)

- **Real public keys** — placeholder docs only. Sprint 5/E1.5 (separate gated PR with Josh-explicit-✅ AEGIS-self-tune-class gate per cosmic-flute §5).
- **Composite GitHub Action `verify-aegis-attestation`** — Sprint 5/E2 (separate plan).
- **Reusable workflow `aegis-verify-attestation.yml`** — Sprint 5/E3 (separate plan).
- **Dogfood integration** (aegis-deploy.yml + openclaw-operator-os blue-green-deploy.sh) — Sprint 6/F1+F2.
- **Org-level GitHub Ruleset enforcement** — Sprint 5/E1.5 admin op.

See [`docs/roadmap.md`](docs/roadmap.md).

## Trust model

This repo is the **single source-of-truth** for AEGIS attestation verification across the 20-repo Undercurrent portfolio. Per cosmic-flute §17 Critical 3 + ADR-011 §Negative §6:

- **CODEOWNERS-protected** on `keys/`, `schema/`, `policy/`, `.github/` (see `.github/CODEOWNERS`)
- **SHA-pinning required** in consumer repos (never `@main`)
- **Org-level GitHub Ruleset** enforces required status checks (Sprint 5/E1.5)
- **Distinct AEGIS instance evaluating policy changes** (Sprint 5/E1.5)

See [`docs/architecture/adr/ADR-001-repo-trust-model.md`](docs/architecture/adr/ADR-001-repo-trust-model.md) for the full threat model + mitigations.

## License

**Apache-2.0** — this is a **client-side verifier kit**. Client libraries ship permissive per industry convention (sigstore, slsa-verifier, in-toto, datadog-agent, vault-action all Apache-2.0). The parent `aegis-governance` SaaS server stays **BSL-1.1** (revenue protection); the verifier kit is intrinsically commodity (Ed25519 + ML-DSA-44 + RFC 8785 + DSSE are open standards, derivable in ~250 LOC from the publicly-vendored schema). See cosmic-flute §26.15 C for the full industry-pattern rationale.

## Reporting security issues

Email `security@undercurrentholdings.com` or use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability).

## Status

`v1.3.0` — the `aegis-enforce.yml` public surface gained the `on_unavailable` and `allowed_api_hosts` inputs, so an unreachable AEGIS API is now distinguishable from a governance denial (the conflation deadlocked `aegis-governance` main during the 2026-06/07 outage). The repository test suite is gated on every PR for the first time. See `CHANGELOG.md`.

Earlier: Sprint 6/F1 SHIP COMPLETE + §38 forensic-audit chain (aegis-governance v1.2.7 in production since 2026-05-21); cumulative ship cycle E1 → E1.5 → E2 → E3 → sub-phase 3a → QG-§37.18 → sub-phase 4 v1.2.6 → §38 v1.2.7.
