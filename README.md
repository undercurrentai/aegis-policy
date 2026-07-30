# AEGIS Policy

Verifier kit + canonical trust roots for AEGIS cryptographic attestations (per [ADR-011](https://github.com/undercurrentai/aegis-governance/blob/main/docs/architecture/adr/ADR-011-artifact-bound-aegis-attestations.md)).

## What's here

| Path | Purpose |
|---|---|
| `schema/` | Vendored predicate schema v1 + interface-contract `attestation:` section, sourced verbatim from `aegis-governance@a5c0bfd`. Self-contained — consumers don't need to clone the parent repo. |
| `policy/` | **Canonical verifier policy artifact** (`verifier-policy-v1.yaml`). Required algorithms, required keyids, required context bindings, fail-closed conditions, TTL per risk class, nonce policy, policy_version compatibility. Consumers pin this file by **immutable SHA**, never by `@main`. |
| `keys/` | **Canonical Ed25519 + ML-DSA-65 public keys** (real, shipped Sprint 5/E1.5 ceremony 2026-05-12; SHA-256 fingerprints cross-checked against the policy artifact by the fingerprint-parity CI gate). |
| `actions/verify-aegis-attestation/` | **Composite GitHub Action** — offline attestation verification, consumed cross-repo by SHA pin (Sprint 5/E2). |
| `.github/workflows/aegis-verify-attestation.yml` | **Reusable workflow** wrapping the composite (Sprint 5/E3). `aegis-enforce.yml` — the §48 enforce substrate consumed by the portfolio. |
| `docs/` | Trust-model ADR-001, governance summary, key-rotation runbook (full procedure), release discipline, break-glass runbook, roadmap. |
| `scripts/` | Maintenance + gates: error-class parity, fingerprint parity, `verify_action.py` (the composite's entry point). |
| `.github/workflows/` | Test suite (both venv paths, required), lint + CODEOWNERS-validity guard (required), parity gates (required), AEGIS shadow-eval (required), tri-AI second review + auto-approve aggregator, verifier-kit job (advisory). |

Org-level GitHub Ruleset enforcement is live: `aegis-attestation-required-checks` (7 required contexts, `bypass_actors: []`).

See [`docs/roadmap.md`](docs/roadmap.md) for what remains open.

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

Current release: see the top entry of [`CHANGELOG.md`](CHANGELOG.md) (version-agnostic by design — this line went stale twice when it named versions). Highlights as of v1.4.1 (2026-07-30): the required-check set is satisfiable in-band (7 contexts), every CI dependency install is hash-pinned wheel-only from committed lockfiles, the 19 verifier-kit tests run on every PR against the exact-pinned public-PyPI SDK, trust-spine code ownership is team-based with a CODEOWNERS-validity CI guard, and Dependabot alert #1 (GHSA-537c-gmf6-5ccf) is closed end-to-end.

Earlier: Sprint 6/F1 SHIP COMPLETE + §38 forensic-audit chain (aegis-governance v1.2.7 in production since 2026-05-21); cumulative ship cycle E1 → E1.5 → E2 → E3 → sub-phase 3a → QG-§37.18 → sub-phase 4 v1.2.6 → §38 v1.2.7.
