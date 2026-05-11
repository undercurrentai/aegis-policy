# AEGIS Policy Changelog

All notable changes to the `undercurrentai/aegis-policy` repo. Format: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

This is the **repo-level** changelog. The `policy_version` field of `policy/verifier-policy-v1.yaml` is tracked separately in `policy/CHANGELOG.md`.

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
