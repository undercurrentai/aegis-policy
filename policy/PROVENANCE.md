# Verifier Policy Provenance

How `policy/verifier-policy-v1.yaml` was derived. Each field below is traced to a specific upstream source so future maintainers know which fields are policy decisions (locally tunable) vs schema-locked (must mirror upstream).

**Current source-of-truth**: `aegis-governance@7e422b2` (post Sprint 5/E1.5 Phase 4 algorithm migration + post-ship audit PR #171). Previous source for v1.0.0 was `aegis-governance@a5c0bfd`.

## Field-by-field derivation

| Field | Type | Source | Tunable? |
|---|---|---|---|
| `policy_version` | semver | This artifact's own version (independent of repo-level CHANGELOG) | YES — bump on any change to required_* / fail_closed_on / crypto |
| `spec_uri` | URI | Convention: `https://aegis.undercurrentholdings.com/policy/verifier/v<MAJOR>` | NO (convention-locked) |
| `crypto.required_algorithms` | list | ADR-011 §Decision + ADR-012 (Ed25519 + ML-DSA-65 hybrid; algorithm migration from ML-DSA-44 → ML-DSA-65 at Sprint 5/E1.5) | NO (algorithm choice is ADR-locked) |
| `crypto.verification_rule` | literal | ADR-011 §Decision: "AND-of-2" (both signatures must verify) | NO |
| `crypto.context_string` | bytes | `aegis-governance/src/crypto/attestation_provider.py:42` — `b"aegis-attestation-v1"` (unchanged through migration) | NO (must match server's CONTEXT_STRING byte-exactly) |
| `crypto.payload_type` | MIME | `aegis-governance/src/aegis_governance/attestation_models.py PAYLOAD_TYPE` — `application/vnd.in-toto+json` | NO |
| `crypto.{ed25519,mldsa65}_keyid_prefix` | string | `aegis-governance/src/crypto/attestation_provider.py` (post-ADR-012: `ml-dsa-65:` prefix) | NO |
| `crypto.{ed25519,mldsa65}_public_size_bytes` | int | FIPS 204 Table 2 (ML-DSA-65 = 1,952B; ML-DSA-44 = 1,312B obsolete) + Ed25519 RFC 8032 (32B) | NO |
| `crypto.ed25519_binding` | literal | ADR-011 §22.13 dec 5: hash-and-sign workaround (Ed25519 doesn't natively support context strings) — UNCHANGED through migration | NO |
| `crypto.mldsa65_binding` | literal | **ADR-012 §"Context-string binding under KMS"**: uniform prefix-hash-and-sign (`H(CONTEXT_STRING ‖ PAE) → ML-DSA-65 plain sign`). Supersedes ADR-011 N2's "FIPS 204 native ctx-string API" because GCP KMS `asymmetric_sign` does NOT expose a FIPS 204 context-string parameter (only `data` or `digest` fields). | NO |
| `required_keyids` | dict | Sprint 5/E1.5 Phase 1 ceremony output (see ADR-002 of this repo); real SHA-256 fingerprints filled in Phase 5 C4 (`740fb5a`); fingerprint-parity gate enforces bytes ↔ fingerprints invariant on every PR | YES — rotation procedure per `docs/key-rotation-runbook.md` |
| `required_context_bindings` | list | ADR-011 r2 + interface-contract attestation `context_bindings_required` (6 fields) | NO (ADR-locked) |
| `required_predicate_fields` | list | `schema/attestation_predicate_v1.yaml predicate_schema.governance.required` (8 fields) | NO (schema-locked) |
| `ttl_per_risk_class` | dict | Tightened from `interface-contract-attestation-v1.2.0.yaml initial_defaults_hours` (low/medium 24h, high/critical 4h → 1h here for stricter safety margin) | YES — quarterly review against measured P99 pipeline duration + approval SLA |
| `review_cadence` | string | ADR-011 r3 + interface-contract `ttl.review_cadence` | YES |
| `re_attestation_allowed` | bool | ADR-011 r3 + interface-contract `ttl.re_attestation_allowed` | NO (ADR-locked) |
| `nonce_required_for_risk_classes` | list | ADR-011 lines 217-231 + interface-contract `nonce_required_for_risk_classes` | NO |
| `nonce_byte_length` | int | ADR-011: 256-bit (32 bytes) | NO |
| `fail_closed_on` | list | **`aegis-sdk/src/aegis/_verify_local.py` post-Sprint-5/E1.5-Phase-4** — every error_class string the SDK can return must appear here (snake_case-translated). 15 entries on main `7e422b2`. Algorithm migration ML-DSA-44 → ML-DSA-65 did NOT change the taxonomy (parity gate confirms 15-vs-15 PASS pre- and post-migration). | NO — schema-locked + parity-enforced by `error-class-parity.yml` CI workflow |
| `policy_version_compatibility` | literal | ADR-011 N3: strict-equal | YES — could relax to semver-major-equal if churn justifies (would need its own ADR) |
| `replay_detection` | block | Sprint 5/E2 Phase A (task #119): consumer-owned replay-detection contract derived from upstream ADR-011 §"Verifier statelessness" + ADR-001 §"Consumer-owned replay-detection responsibility" (added in Commit 2 of this PR) | NO (contract-locked; composite-action support metadata reflects the action's actual behavior) |

## Tunable-field change procedure

For YES-tunable fields (TTL, keyids, policy_version_compatibility, etc.):

1. Open PR touching `policy/verifier-policy-v1.yaml`
2. **Bump `policy_version`** in the same file (semver: MINOR for backward-compatible additions, MAJOR for any field removal/contract tightening)
3. Add entry to `policy/CHANGELOG.md` describing what changed + why
4. CODEOWNERS review required (`@ThermoclineLeviathan`)
5. AEGIS Stage-2 self-eval (governance-mutating change → likely PROCEED w/ override per Sprint 1-5 pattern)
6. `error-class-parity.yml` will run automatically; if `fail_closed_on` was touched, parity must hold against latest SDK
7. `fingerprint-parity.yml` runs automatically when `keys/` or `policy/verifier-policy-v1.yaml required_keyids` is touched
8. Coordinate with all 20 consumer repos pinning the previous SHA — they'll need to bump their pin in their next routine PR (no immediate cutover required if `policy_version_compatibility` is `strict-equal` because consumers staying on the old SHA still work)

## NO-tunable-field change procedure

For schema-locked fields (algorithms, context_string, key sizes, error_class taxonomy, etc.):

1. **First** open a PR on `aegis-governance` updating the source-of-truth (schema, ADR, attestation_provider.py)
2. Wait for that to merge + freeze-tag bump
3. Then open a PR here vendoring the new schema + bumping `policy/verifier-policy-v1.yaml policy_version` MAJOR
4. Coordinate consumer-repo pin bumps before the schema-locked field actually changes in production

## Schema vendoring source bumps

| `policy_version` | Vendored schema source SHA | Vendored SDK source SHA | Notes |
|---|---|---|---|
| 1.0.0 (2026-05-09) | `aegis-governance@a5c0bfd` (Sprint 1 squash-merge) | `aegis-governance@37f8608` (Sprint 4/D2 audit-pass) | Bootstrap; placeholder fingerprints; ml-dsa-44 algorithm |
| 2.0.0 (2026-05-10) | `aegis-governance@7e422b2` (Sprint 5/E1.5 Phase 4 + audit PR #171) | `aegis-governance@7e422b2` | BREAKING: ml-dsa-44 → ml-dsa-65; real fingerprints; uniform prefix-hash-and-sign per ADR-012 |
| 2.1.0 (2026-05-13) | `aegis-governance@dc9c9df` (post-v1.2.4) — unchanged | `aegis-governance@dc9c9df` — unchanged | MINOR additive: `replay_detection:` block + ADR-001 §"Consumer-owned replay-detection responsibility". No schema/SDK changes; SDK ↔ policy parity preserved (15 vs 15). |
