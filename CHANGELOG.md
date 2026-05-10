# AEGIS Policy Changelog

All notable changes to the `undercurrentai/aegis-policy` repo. Format: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

This is the **repo-level** changelog. The `policy_version` field of `policy/verifier-policy-v1.yaml` is tracked separately in `policy/CHANGELOG.md`.

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
