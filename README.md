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

`v1.2.7` — Sprint 7/G1 SHIP COMPLETE: the org-wide AEGIS-gate enforce substrate is live in **shadow** mode (org-Ruleset `aegis-enforce-required-check` `17101026`, `bypass_actors=[]`) on both source repos, the cross-repo `resolve_callee` fix shipped (§51, `v1.2.6`), and the §44 Phase 2 tri-AI second-reviewer aggregator now auto-approves routine PRs (3-AI consensus + trust-spine carve-out + change_class gate). aegis-governance `v1.2.7` in production since 2026-05-21. Sprint 7/G2-G3 (consumer rollout) unblocked at the architectural-contract layer. See `CHANGELOG.md` + `docs/roadmap.md` for the cumulative ship cycle (E1 → E1.5 → E2 → E3 → §48 relocation → §51 cross-repo fix → §44 Phase 2 auto-approve).
