# Schema Provenance

This directory vendors schema files from the parent `aegis-governance` repo. Each file is committed verbatim from a specific upstream commit so consumers can verify byte-exact parity with the server-side contract.

## Vendored files

| File | Source repo | Source path | Source commit (SHA) | Vendored on | Notes |
|---|---|---|---|---|---|
| `attestation_predicate_v1.yaml` | `undercurrentai/aegis-governance` | `schema/attestation_predicate_v1.yaml` | `a5c0bfd6379f85d506ff47656aa4ee4ec5eb56a4` (Sprint 1, 2026-05-08) | 2026-05-09 | Verbatim copy. Frozen by tag `aegis-attestation-predicate-v1-freeze` (line 7 of the schema). |
| `interface-contract-attestation-v1.2.0.yaml` | `undercurrentai/aegis-governance` | `schema/interface-contract.yaml` (lines 138-251 only — the `attestation:` block) | `a5c0bfd6379f85d506ff47656aa4ee4ec5eb56a4` (Sprint 1, 2026-05-08) | 2026-05-09 | Extracted verbatim. Parent's `parameters:` and `aliases:` blocks are out-of-scope for verifier kit consumers and intentionally omitted. |

## Refresh procedure

When `aegis-governance` bumps the schema (next freeze-tag bump):

1. Open a PR on this repo updating both vendored files + this `PROVENANCE.md` SHA.
2. Update `schema/CHANGELOG` not present here (we use the repo-level `CHANGELOG.md` + `policy/CHANGELOG.md`); summarize the upstream bump in the next `[X.Y.Z]` entry of the **repo-level** `CHANGELOG.md`.
3. If the schema bump changes the predicate's required-fields set, **bump `policy/verifier-policy-v1.yaml policy_version`** and add an entry to `policy/CHANGELOG.md`.
4. The `error-class-parity.yml` workflow auto-checks the SDK ↔ policy invariant; the schema refresh PR will fail this check until the policy artifact catches up.
5. CODEOWNERS (`@ThermoclineLeviathan`) review required; AEGIS Stage-2 self-eval submitted before merge.

## Drift detection

A future workflow (Sprint 5/E1.5 or E2) will automatically diff vendored files against the upstream commit by SHA + alert on drift. Today this is a manual quarterly check coordinated with the `policy/verifier-policy-v1.yaml ttl_per_risk_class review_cadence`.

## Why vendor instead of submodule?

- **Self-contained**: consumers don't need to clone `aegis-governance` (which is a private BSL-1.1 repo; some external integrators won't have access).
- **Auditability**: every byte is in this public repo's git history; no opaque submodule ref to chase.
- **Refresh cadence is low**: the predicate schema is freeze-tagged (`v1.0.0` lifetime measured in years). Submodule overhead vs annual manual refresh is unfavorable.
