# Verifier Policy Changelog

Tracks `policy/verifier-policy-v1.yaml policy_version` bumps independently of the repo-level `CHANGELOG.md`. This separation lets consumers pin a specific `policy_version` without coupling to repo-level bookkeeping.

Format: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html) — MAJOR for field removal / contract tightening, MINOR for backward-compatible additions, PATCH for documentation-only fixes within an entry.

---

## [2.1.0] — 2026-05-13

**Sprint 5/E2 Phase A** — closes task #119 (consumer-owned replay-detection design dependency surfaced by post-ship /quality-gate Phase 3 ultrathink U1 on v1.2.4).

### Added

- **`replay_detection:` top-level block** documenting the consumer-owned replay-detection contract. AEGIS verifier (server-side `/attestations/verify` + SDK offline `verify_attestation_locally`) is STATELESS by design per upstream ADR-011 §"Verifier statelessness". Replay detection is consumer-owned. The new block specifies: policy (`consumer-owned`); primary mechanism (`decision-id-uniqueness` — all risk classes); secondary mechanism (`nonce-uniqueness` — high/critical only); enforcement layer (`consumer-ci-workflow`); 3 recommended stores (append-only file / DB unique constraint / Redis SETNX); composite-action support metadata (the `verify-aegis-attestation@<sha>` action accepts an optional `replay-store-path` input that implements the append-only-file mechanism for consumers without their own store).

### Documentation

- **ADR-001 §"Consumer-owned replay-detection responsibility"** new subsection under §Decision documents the responsibility split + implementation guidance (per Sprint 5/E2 Commit 2).

### Compatibility

- **`fail_closed_on:` unchanged at 15 entries** — replay-detection emits `AttestationReplayDetected` from the composite-action layer, NOT the verifier layer. SDK ↔ policy parity invariant preserved (parity gate still 15 vs 15; no SDK re-vendor needed).
- **MINOR per SemVer** — additive contract field; consumers pinning v2.0.0 continue to function unchanged. Migration is opt-in: consumers wanting replay-detection bump their aegis-policy pin to this PR's merge SHA + add `replay-store-path` input to their workflow.

### Upstream

- Cosmic-flute plan §34: `~/.claude/plans/let-s-plan-this-cosmic-flute.md`
- ADR-011 upstream: `https://github.com/undercurrentai/aegis-governance/blob/main/docs/architecture/adr/ADR-011-artifact-bound-aegis-attestations.md`
- SDK source-of-truth: `aegis-sdk@1.0.0` (`aegis-governance` main `dc9c9df` — post v1.2.4)

---

## [2.0.0] — 2026-05-10

**BREAKING** — Algorithm migration ML-DSA-44 → ML-DSA-65 per upstream [ADR-012](https://github.com/undercurrentai/aegis-governance/blob/main/docs/architecture/adr/ADR-012-ml-dsa-44-to-65-migration.md); real key fingerprints replace placeholders. Sprint 5/E1.5 Phase 5 ship.

### Changed

- **Algorithm**: `crypto.required_algorithms` → `[ed25519, ml-dsa-65]` (was `[ed25519, ml-dsa-44]`)
- **Keyid prefix**: `mldsa65_keyid_prefix: "ml-dsa-65:"` (was `mldsa44_keyid_prefix: "ml-dsa-44:"`)
- **Public-key size**: `mldsa65_public_size_bytes: 1952` (was `mldsa44_public_size_bytes: 1312`)
- **Signature binding**: `mldsa65_binding: prefix_hash_sign` (was `mldsa44_binding: native_ctx_str`). Per upstream ADR-012 §"Context-string binding under KMS": GCP KMS `asymmetric_sign` does NOT expose a FIPS 204 ctx-string parameter; uniform prefix-hash-and-sign (`H(CONTEXT_STRING ‖ PAE) → ML-DSA-65 plain sign`) is byte-for-byte equivalent under random-oracle assumption.
- **Required keyids**: real SHA-256 hex fingerprints replace `PLACEHOLDER_E1_5_CEREMONY_PENDING`:
  - `ed25519: 33378f58b12a92488fd57888323b77fef2ffd9bd051c10768fc770c02025d97d`
  - `mldsa65: f4e65bb77a508e82cd60b576075866d3e6447f4d3fd841ef1c3f1b93ecbe7d93`

### Added

- **Fingerprint-parity CI gate** (`scripts/check_fingerprints.py` + `.github/workflows/fingerprint-parity.yml`): cross-checks `policy/verifier-policy-v1.yaml required_keyids` against SHA-256 over `keys/ed25519-public.pem` + `keys/mldsa65-public.bin` on every PR. Closes the single-char-typo failure mode that would otherwise cause a live deploy outage.
- **ADR-002** (`docs/architecture/adr/ADR-002-key-ceremony-2026-05-10.md`): key ceremony log — KMS-internal generation at SOFTWARE protection (HSM unavailable for both `EC_SIGN_ED25519` and `PQ_SIGN_ML_DSA_65`); captured fingerprints; AEGIS Stage-2 decision_id `9eae3455…` ESCALATE → OVERRIDE_APPLIED per cosmic-flute §28.5.1.
- **ADR-003** (`docs/architecture/adr/ADR-003-ml-dsa-44-to-65-migration.md`): repo-local algorithm-migration consequence ADR (downstream of upstream ADR-012); consumer migration table; verifier behavior table; v1.0.0 vs v2.0.0 BREAKING changes table.

### Migration

Any consumer pinning aegis-policy at v1.0.0 SHA (`9c25b38` from Sprint 5/E1 OR `8de3e14` from post-merge status flip) MUST bump explicitly to this PR's merge SHA to consume v2.0.0. Migration steps:

1. Update the pinned aegis-policy SHA in `.github/workflows/aegis-verify-attestation.yml` (or equivalent).
2. Refresh any locally-cached copies of `keys/ed25519-public.pem` + `keys/mldsa65-public.bin`.
3. If using the SDK runtime, ensure `aegis-governance[verify] >= 1.0.0` (NOT 0.6.x — the SDK wire-format break is documented in upstream `aegis-sdk/CHANGELOG.md` [1.0.0] BREAKING entry).
4. Re-attest any artifacts signed pre-migration: ML-DSA-44 signatures are NOT forward-compatible with ML-DSA-65 verifiers + vice versa.

No consumer currently pins aegis-policy as of 2026-05-10 (Sprint 6 dogfood loop hasn't started). Sprint 6/F1+F2 will pin directly to this Phase 5 merge SHA, skipping v1.0.0.

### Upstream

- Cosmic-flute plan §28 + §30: `~/.claude/plans/let-s-plan-this-cosmic-flute.md`
- Upstream ADR-012: `https://github.com/undercurrentai/aegis-governance/blob/main/docs/architecture/adr/ADR-012-ml-dsa-44-to-65-migration.md`
- SDK source-of-truth: `aegis-sdk@1.0.0` (`aegis-governance` main `7e422b2`)

---

## [1.0.0] — 2026-05-09

Initial canonical verifier policy artifact. Sprint 5/E1 ship.

### Defined

- **Crypto contract**: Ed25519 + ML-DSA-44 hybrid AND-of-2 per ADR-011; CONTEXT_STRING `aegis-attestation-v1`; payload_type `application/vnd.in-toto+json`; key sizes (Ed25519 32B, ML-DSA-44 1312B).
- **Required keyids**: PLACEHOLDER fingerprints — real values land in Sprint 5/E1.5 ceremony. Until E1.5, this policy artifact is **not consumable for verification** by E2/E3 (they will fail with placeholder check).
- **Required context bindings** (6): repository, workflow_ref, run_id, run_attempt, environment, subject_digest.
- **Required predicate fields** (8): decision_id, artifact_digest, environment, risk_class, policy_version, issued_at, expires_at, gate_pass_states.
- **TTL per risk_class**: low/medium 24h, high/critical 1h. Quarterly-review cadence; next review 2026-08-09.
- **Nonce policy**: required for `high` and `critical` risk_class; 32-byte (256-bit).
- **Fail-closed conditions** (15): full SDK error_class taxonomy mirror, parity-enforced by `error-class-parity.yml` CI workflow.
- **Policy_version_compatibility**: `strict-equal` (consumers pinning v1.0.0 must verify only against v1.0.0 attestations).

### Notes

- The 15-entry `fail_closed_on` list mirrors the post-Sprint-4/D2-audit SDK on `aegis-governance` main `37f8608`. Cosmic-flute §26.18 documents one judgment-call deviation from the Ultraplan refinement: Ultraplan recommended a 14-entry list dropping `signature_set_incomplete` on the assumption that envelope shape errors raise `ValueError`. Post-audit (commit `7700ce0` inside PR #168) the SDK returns `(False, "AttestationSignatureSetIncomplete")`. SDK source is the source-of-truth; 15 entries is correct.

### Upstream

- Cosmic-flute plan §26: `~/.claude/plans/let-s-plan-this-cosmic-flute.md`
- ADR-011: `https://github.com/undercurrentai/aegis-governance/blob/main/docs/architecture/adr/ADR-011-artifact-bound-aegis-attestations.md`
- SDK source-of-truth: `aegis-sdk@v0.6.1` (`aegis-governance` main `37f8608`)
