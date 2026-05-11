# ADR-003 — ML-DSA-44 → ML-DSA-65 algorithm migration (consequence of upstream ADR-012)

**Status**: Accepted | 2026-05-10
**Authors**: Joshua Kirby (sole-keyholder per ADR-001 growth path)
**Supersedes**: N/A (algorithm choice was set in ADR-011 upstream; this ADR records the migration consequence on aegis-policy)

## Context

Upstream `aegis-governance` migrated its attestation crypto from ML-DSA-44 → ML-DSA-65 in Sprint 5/E1.5 Phase 4 (PR #169 squashed to commit `6798304`; post-ship audit PR #171 squashed to commit `7e422b2`). The migration is fully documented in upstream `docs/architecture/adr/ADR-012-ml-dsa-44-to-65-migration.md`.

This repo-local ADR records the downstream consequence for aegis-policy:

1. The vendored `scripts/_verify_local_vendored.py` was re-vendored from `aegis-governance@7e422b2` (Phase 5 C1; commit `4b7a530`), replacing the pre-migration copy from `aegis-governance@37f8608`.
2. The verifier-policy artifact `policy/verifier-policy-v1.yaml` was algorithm-renamed + version-bumped (Phase 5 C2; commit `1f3a4a3`): `ml-dsa-44` → `ml-dsa-65`; 1312B → 1952B; `policy_version: 1.0.0 → 2.0.0` (MAJOR per SemVer).
3. Real fingerprints replaced `PLACEHOLDER_E1_5_CEREMONY_PENDING` (Phase 5 C4; commit `740fb5a`) using bytes from the Sprint 5/E1.5 Phase 1 key ceremony (see ADR-002).
4. A new fingerprint-parity CI gate (Phase 5 C5) enforces bytes ↔ fingerprints invariant.

### Why this ADR exists (separate from ADR-002)

ADR-002 documents the **provenance + threat-model acceptance** for the specific key bytes. ADR-003 documents the **algorithm migration consequence** on aegis-policy artifacts. They serve different audit purposes:
- ADR-002 answers: "where did these bytes come from + why is SOFTWARE protection acceptable?"
- ADR-003 answers: "what's different between aegis-policy v1.0.0 and v2.0.0, and how do consumers migrate?"

## Decision

aegis-policy v2.0.0 ships with the following BREAKING changes vs v1.0.0:

| Surface | v1.0.0 (pre-migration) | v2.0.0 (post-migration) |
|---|---|---|
| `required_algorithms` | `[ed25519, ml-dsa-44]` | `[ed25519, ml-dsa-65]` |
| Keyid prefix (ML-DSA) | `ml-dsa-44:` | `ml-dsa-65:` |
| ML-DSA public key size | 1,312 bytes | **1,952 bytes** |
| ML-DSA signature size | 2,420 bytes | **3,309 bytes** |
| FIPS 204 security level | Level 2 (128-bit PQ) | **Level 3 (192-bit PQ; NIST default)** |
| Signing scheme (verifier-side) | FIPS 204 native ctx-string (`verify_with_ctx_str`) | **Uniform prefix-hash-and-sign** (`oqs.Signature("ML-DSA-65").verify(H(ctx ‖ pae), …)`) |
| `required_keyids` | `PLACEHOLDER_E1_5_CEREMONY_PENDING` (both) | Real SHA-256 hex (both); see ADR-002 |
| Vendored verifier source | `aegis-governance@37f86089…` | `aegis-governance@7e422b2…` |

### Wire-format break detail

The most consequential change is the **verifier behavior shift to uniform prefix-hash-and-sign**. Per upstream ADR-012 §"Context-string binding under KMS":

> GCP Cloud KMS `asymmetric_sign` API does NOT expose a FIPS 204 ctx-string parameter (only `data` or `digest` fields). The KMS server, when signing ML-DSA-65, internally uses an empty default context per FIPS 204 Algorithm 2. To preserve the cross-protocol-misuse defense that an explicit context-string would provide, the issuer-side signer pre-hashes `msg' = SHA-256(CONTEXT_STRING ‖ PAE)` and signs `msg'` as `data`. The SDK-side verifier mirrors: `oqs.Signature("ML-DSA-65").verify(H(CONTEXT_STRING ‖ PAE), sig, pubkey)` — NOT `verify_with_ctx_str(...)`.

This is **byte-for-byte equivalent** to FIPS 204 ctx-string mode with empty default context under the standard random-oracle assumption, and was empirically verified during Phase 4a smoke probe (cosmic-flute §28.18.3; gcloud CLI + Python client transports both confirmed sign-then-verify-locally roundtrip).

For aegis-policy specifically: this shift means the vendored verifier (`scripts/_verify_local_vendored.py` post Phase 5 C1) uses `oqs.Signature.verify()` not `verify_with_ctx_str()`. Pre-existing scripts/tools that relied on the FIPS 204 native ctx-string API would break — but no such tools exist in aegis-policy (the only consumer of the vendored verifier is `scripts/check_error_class_parity.py` which AST-walks the file for error_class strings, not for runtime behavior).

## Consumer migration

Any consumer repo currently pinning aegis-policy at v1.0.0 SHA (`9c25b38` or `8de3e14`) MUST bump explicitly to the Phase 5 merge SHA (filled in post-merge) to consume v2.0.0. Migration steps for consumers:

1. Update the pinned aegis-policy SHA in `.github/workflows/aegis-verify-attestation.yml` (or equivalent).
2. Refresh any locally-cached copies of `keys/ed25519-public.pem` + `keys/mldsa65-public.bin`.
3. If the consumer uses the SDK runtime (`aegis-governance[verify]`), ensure they're on aegis-sdk 1.0.0+ (NOT 0.6.x — the SDK API includes the wire-format break documented in upstream `aegis-sdk/CHANGELOG.md` [1.0.0] BREAKING entry).
4. Re-attest any artifacts signed pre-migration: ML-DSA-44 signatures are NOT forward-compatible with ML-DSA-65 verifiers + vice versa.

No consumer pins aegis-policy as of 2026-05-10 (Sprint 6 dogfood loop hasn't started). When Sprint 6/F1+F2 begin, the FIRST consumer pin will target the Phase 5 merge SHA directly (skipping v1.0.0 entirely) — the pre-migration v1.0.0 was always intended as a bootstrap-only staging point.

## Verifier behavior table (for downstream Sprint 6+ consumers)

When a consumer's pinned verifier-kit invocation observes a DSSE envelope, the matching against `policy/verifier-policy-v1.yaml` proceeds as follows:

| Envelope condition | v2.0.0 verifier action |
|---|---|
| signature uses `keyid: "ml-dsa-44:..."` | FAIL CLOSED — `mldsa_verify_failed` (algorithm not in required_algorithms) |
| signature uses `keyid: "ml-dsa-65:..."` but pubkey is 1312B | FAIL CLOSED — `mldsa_verify_failed` (size mismatch; OQS verify rejects) |
| signature uses `keyid: "ml-dsa-65:..."` + pubkey is 1952B + fingerprint matches `required_keyids.mldsa65` | proceed to crypto verify |
| crypto verify uses `verify_with_ctx_str(pae, ctx, sig, pk)` | FAIL — signature was produced via prefix-hash-and-sign per ADR-012; ctx-string mode reads wrong message |
| crypto verify uses `verify(H(ctx ‖ pae), sig, pk)` | proceed — matches the issuer-side signing path |
| Ed25519 + ML-DSA-65 both verify against the policy-pinned pubkeys | AND-of-2 passes; envelope accepted |

The `fail_closed_on` taxonomy is UNCHANGED from v1.0.0 to v2.0.0 (15 entries; the algorithm rename did not introduce any new failure modes). This was empirically verified in Phase 5 C1: `scripts/check_error_class_parity.py` STILL exits 0 with `15 vs 15 ✓ PARITY HOLDS` after the re-vendor.

## Consequences

**Positive:**
- Stronger PQ security (FIPS 204 Level 3 vs Level 2; NIST-recommended default)
- Uniform crypto floor across the AEGIS attestation surface (both issuer + SDK + this policy artifact now agree on prefix-hash-and-sign for both algorithms)
- Provisioned in GCP KMS today (no PyPI dependency on a possibly-unstable preview API)
- Trust-spine fingerprints anchored to canonical KMS-resident keys (ADR-002)

**Negative:**
- Larger sigs (+37%; 2,420B → 3,309B) — negligible at attestation scale
- Larger pubkeys (+49%; 1,312B → 1,952B) — one-shot cost in keys/ + on-disk verifier kit
- DSSE keyid prefix break (`ml-dsa-44:` → `ml-dsa-65:`) — forced consumer SHA bump; acceptable since no production consumer exists yet

**Accepted (per AEGIS Stage-2 decision_id `9eae3455…` per ADR-002):**
- Sprint 5/E1.5 bundled the algorithm migration into the same gated PR cycle as the key ceremony — minimizing the cumulative coordination cost of multiple breaking changes.

## References

- Upstream ADR-012 (canonical algorithm-migration ADR) — aegis-governance@`7e422b2`:`docs/architecture/adr/ADR-012-ml-dsa-44-to-65-migration.md`
- Upstream ADR-011 (artifact-bound AEGIS attestations + N4 distinct-keys invariant) — aegis-governance@`7e422b2`:`docs/architecture/adr/ADR-011-artifact-bound-aegis-attestations.md`
- Upstream `aegis-sdk/CHANGELOG.md` [1.0.0] BREAKING entry (aegis-governance@`7e422b2`)
- ADR-001 — Repo trust model (this repo)
- ADR-002 — Sprint 5/E1.5 key ceremony (this repo; companion document)
- cosmic-flute §28.3 + §28.17 + §30 (planning + Phase 1 capture + Phase 5 execution)
- Phase 5 commits: C1 `4b7a530` (re-vendor); C2 `1f3a4a3` (algorithm rename + v2.0.0); C3 `9094904` (key bytes); C4 `740fb5a` (real fingerprints); C5 (fingerprint-parity gate); C6 (this ADR + ADR-002)

## Changelog

| Date | Author | Change |
|---|---|---|
| 2026-05-10 | Claude Opus 4.7 (1M) / Josh Kirby | Initial draft (Status: Accepted post-PR merge per ADR-001 conventions) |
