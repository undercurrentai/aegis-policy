# Key Rotation Runbook (stub)

Procedure for rotating the canonical Ed25519 + ML-DSA-44 attestation keys. **Full ceremony details land in Sprint 5/E1.5** (separate gated PR with Josh-explicit-✅ AEGIS-self-tune-class gate per cosmic-flute §5).

## Status

`v0.1.0 STUB` — this runbook is intentionally incomplete at E1. The actual mechanics (offline keygen environment, GCP KMS alias provisioning, wrap-and-rewrap rollover window, consumer-repo SHA-pin sync) are determined during the E1.5 ceremony and committed in the same E1.5 PR that lands the first real keys.

## Why a stub?

E1 ships the **repo + governance scaffolding**. E1.5 ships the **first key ceremony**. Bundling both into one PR would:
- Inflate review surface beyond what one PR can be safely audited for
- Couple the (uncontroversial) repo-bootstrap to the (high-stakes) keygen ceremony
- Skip the AEGIS-self-tune-class gate that key generation requires

Splitting them lets E1 ship cheap (governance only) and E1.5 ship safe (real keys with explicit gates).

## E1.5 ceremony scope (placeholder — to be filled in during E1.5 plan)

1. **Offline keygen environment**: TODO E1.5 — air-gapped machine specs, OS, key-generation tooling (`openssl genpkey -algorithm ED25519` for Ed25519; `oqs-py` for ML-DSA-44)
2. **GCP KMS alias provisioning**: TODO E1.5 — create `aegis-attestation-ed25519` + `aegis-attestation-mldsa44` aliases per ADR-011 N4 (distinct from override-workflow keys, disjoint IAM principals)
3. **Server-side rewire**: TODO E1.5 — remove `aegis-governance/src/aegis_governance/attestation_keys.py:155 NotImplementedError` for production KMS path; add integration test
4. **Public-key commit to this repo**: TODO E1.5 — `keys/ed25519-public.pem` + `keys/mldsa44-public.bin`; bump `policy/verifier-policy-v1.yaml required_keyids` fingerprints; `policy/CHANGELOG.md` entry
5. **CODEOWNERS approval**: `@ThermoclineLeviathan` reviews; AEGIS Stage-2 self-eval submitted (governance-mutating + AEGIS-self-tune class → expect Josh-explicit-✅ override per cosmic-flute §5)
6. **Consumer-repo SHA pin updates**: TODO E1.5 — coordinate across the 19 portfolio repos; can lag the merge by their next routine PR cycle since `policy_version_compatibility: "strict-equal"` keeps old-pin consumers on old behavior

## Post-E1.5 ongoing rotation procedure (placeholder)

Once E1.5 lands, the steady-state rotation procedure (every N years or on suspected compromise) follows the same template:

1. Generate new keypairs offline
2. Provision new KMS aliases (don't reuse old ones; rotate aliases to avoid version-mismatch races)
3. Server-side: configure dual-key signing for the rollover window (issue under both old + new keys for `max_ttl_hours = 24h`)
4. Commit new public keys + bump `policy_version` MAJOR (since `required_keyids` changed)
5. CODEOWNERS approval, AEGIS Stage-2 self-eval, merge
6. Consumer-repo SHA pin updates within rollover window
7. After 24h: server stops issuing under old keys; old public-key files remain in git history (for audit) but are removed from `keys/` and `policy/required_keyids` in a follow-up cleanup PR

## Suspected compromise

If a private key is suspected compromised:

1. **Immediately** email `security@undercurrentholdings.com` + open private GitHub vulnerability report — do NOT open a public issue or PR
2. Server-side: revoke the compromised KMS key version in GCP KMS (existing attestations issued under that key fail-closed at verification)
3. Trigger emergency rotation per the steady-state procedure above; rollover window may be compressed below 24h depending on incident severity
4. Post-incident: ADR documenting the compromise + lessons learned

## References

- ADR-011 §Negative §6: verifier-kit + policy-artifact concentration risk
- ADR-011 N4: distinct attestation signing keys vs override-workflow keys
- Cosmic-flute §5: AEGIS thresholds (key rotation = AEGIS-self-tune class, requires Josh-explicit-✅)
- Cosmic-flute §26.13: out-of-scope items deferred to E1.5
- Cosmic-flute §17 Critical 3: policy-bootstrap protection
