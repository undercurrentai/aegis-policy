# Verifier Policy Provenance

How `policy/verifier-policy-v1.yaml` was derived. Each field below is traced to a specific upstream source so future maintainers know which fields are policy decisions (locally tunable) vs schema-locked (must mirror upstream).

## Field-by-field derivation

| Field | Type | Source | Tunable? |
|---|---|---|---|
| `policy_version` | semver | This artifact's own version (independent of repo-level CHANGELOG) | YES — bump on any change to required_* / fail_closed_on / crypto |
| `spec_uri` | URI | Convention: `https://aegis.undercurrentholdings.com/policy/verifier/v<MAJOR>` | NO (convention-locked) |
| `crypto.required_algorithms` | list | ADR-011 §Decision (Ed25519 + ML-DSA-44 hybrid per ADR-003 PQ floor) | NO (algorithm choice is ADR-locked) |
| `crypto.verification_rule` | literal | ADR-011 §Decision: "AND-of-2" | NO |
| `crypto.context_string` | bytes | `aegis-governance/src/crypto/attestation_provider.py:42` — `b"aegis-attestation-v1"` | NO (must match server's CONTEXT_STRING byte-exactly) |
| `crypto.payload_type` | MIME | `aegis-governance/src/aegis_governance/attestation_models.py PAYLOAD_TYPE` — `application/vnd.in-toto+json` | NO |
| `crypto.{ed25519,mldsa44}_keyid_prefix` | string | `aegis-governance/src/crypto/attestation_provider.py:45-46` | NO |
| `crypto.{ed25519,mldsa44}_public_size_bytes` | int | FIPS 204 + Ed25519 spec literals (32, 1312) | NO |
| `crypto.ed25519_binding` | literal | ADR-011 §22.13 dec 5: hash-and-sign workaround (Ed25519 doesn't natively support context strings) | NO |
| `crypto.mldsa44_binding` | literal | ADR-011 N2: FIPS 204 final ctx-string API | NO |
| `required_keyids` | dict | E1.5 ceremony output (placeholders today) | YES — rotation procedure per `docs/key-rotation-runbook.md` |
| `required_context_bindings` | list | ADR-011 r2 + interface-contract attestation `context_bindings_required` (6 fields) | NO (ADR-locked) |
| `required_predicate_fields` | list | `schema/attestation_predicate_v1.yaml predicate_schema.governance.required` (8 fields) | NO (schema-locked) |
| `ttl_per_risk_class` | dict | Tightened from `interface-contract-attestation-v1.2.0.yaml initial_defaults_hours` (low/medium 24h, high/critical 4h → 1h here for stricter safety margin) | YES — quarterly review against measured P99 pipeline duration + approval SLA |
| `review_cadence` | string | ADR-011 r3 + interface-contract `ttl.review_cadence` | YES |
| `re_attestation_allowed` | bool | ADR-011 r3 + interface-contract `ttl.re_attestation_allowed` | NO (ADR-locked) |
| `nonce_required_for_risk_classes` | list | ADR-011 lines 217-231 + interface-contract `nonce_required_for_risk_classes` | NO |
| `nonce_byte_length` | int | ADR-011: 256-bit (32 bytes) | NO |
| `fail_closed_on` | list | **`aegis-sdk/src/aegis/_verify_local.py` post-Sprint-4/D2-audit** — every error_class string the SDK can return must appear here (snake_case-translated). 15 entries on main `37f8608`. | NO — schema-locked + parity-enforced by `error-class-parity.yml` CI workflow |
| `policy_version_compatibility` | literal | ADR-011 N3: strict-equal | YES — could relax to semver-major-equal if churn justifies (would need its own ADR) |

## Tunable-field change procedure

For YES-tunable fields (TTL, keyids, policy_version_compatibility, etc.):

1. Open PR touching `policy/verifier-policy-v1.yaml`
2. **Bump `policy_version`** in the same file (semver: MINOR for backward-compatible additions, MAJOR for any field removal/contract tightening)
3. Add entry to `policy/CHANGELOG.md` describing what changed + why
4. CODEOWNERS review required (`@ThermoclineLeviathan`)
5. AEGIS Stage-2 self-eval (governance-mutating change → likely PROCEED w/ override per Sprint 1-4 pattern)
6. `error-class-parity.yml` will run automatically; if `fail_closed_on` was touched, parity must hold against latest SDK
7. Coordinate with all 19 consumer repos pinning the previous SHA — they'll need to bump their pin in their next routine PR (no immediate cutover required if `policy_version_compatibility` is `strict-equal` because consumers staying on the old SHA still work)

## NO-tunable-field change procedure

For schema-locked fields (algorithms, context_string, key sizes, etc.):

1. **First** open a PR on `aegis-governance` updating the source-of-truth (schema, ADR, attestation_provider.py)
2. Wait for that to merge + freeze-tag bump
3. Then open a PR here vendoring the new schema + bumping `policy/verifier-policy-v1.yaml policy_version` MAJOR
4. Coordinate consumer-repo pin bumps before the schema-locked field actually changes in production
