# Trust Roots — Canonical AEGIS Attestation Public Keys

This directory will contain the canonical Ed25519 + ML-DSA-44 public keys that consumers use to verify AEGIS attestations. **Sprint 5/E1 (this ship) does NOT include real keys** — only this README. Real keys land in Sprint 5/E1.5 ceremony (separate plan, gated by Josh-explicit-✅ AEGIS-self-tune-class per cosmic-flute §5).

## Planned files (Sprint 5/E1.5)

| File | Format | Size | Purpose |
|---|---|---|---|
| `ed25519-public.pem` | PEM-wrapped raw Ed25519 public key | 32B raw / ~120B PEM | Consumer pins via SHA-256 fingerprint; E2 verifier kit reads via `cryptography.hazmat.primitives.serialization.load_pem_public_key` |
| `mldsa44-public.bin` | Raw ML-DSA-44 public key (no standard PEM exists) | 1312B | Consumer pins via SHA-256 fingerprint; E2 verifier kit reads via `oqs.Signature("ML-DSA-44")` (post-`liboqs-python>=0.14.1`) |

## Why two different formats?

- **Ed25519** has standard PEM encoding (RFC 8410) supported by `cryptography`, `openssl`, OpenSSH, etc. PEM is the obvious choice — tooling-friendly + auditable.
- **ML-DSA-44** is a NIST FIPS 204 final post-quantum scheme. As of 2026-05-09 there is **no standard PEM/DER encoding** for ML-DSA public keys. We commit raw 1312-byte material as `.bin`. The format is documented in `liboqs-python` and matches the bytes the verifier consumes via `oqs.Signature.verify_with_ctx_str(message, signature, context, public_key)`.

## Pinning model

Per cosmic-flute §17 Critical 3 + ADR-011 §Negative §6 mitigations: consumers pin this repo by **immutable commit SHA**, never by `@main`. The E2 composite GitHub Action (`actions/verify-aegis-attestation/action.yml`, future) will:

1. Resolve the pinned SHA via `actions/checkout`
2. Read both key files from `keys/`
3. Compute SHA-256 fingerprint of each
4. Compare against caller-supplied `ed25519-key-sha` + `mldsa44-key-sha` action inputs (defaults: the fingerprints embedded in the action.yml at the same SHA)
5. Pass keys to the verifier script (`scripts/verify.py` in E2)

This dual-pinning (SHA on the repo + SHA-256 on the keys) makes silent key-substitution impossible: an attacker would need to (a) push to this repo (CODEOWNERS-protected) AND (b) update the consumer's pinned SHA (still requires consumer-repo CODEOWNERS approval).

## Rotation procedure

See `docs/key-rotation-runbook.md`. Summary (full mechanics defined in E1.5):

1. **Generate** new Ed25519 + ML-DSA-44 keypairs offline on a trusted machine
2. **Store** private keys in GCP KMS aliases (`aegis-attestation-ed25519`, `aegis-attestation-mldsa44` per ADR-011 N4 — distinct from override-workflow keys, disjoint IAM)
3. **Commit** new public keys to this directory (`ed25519-public.pem`, `mldsa44-public.bin`)
4. **Update** `policy/verifier-policy-v1.yaml required_keyids` fingerprints + bump `policy_version`
5. **Update** `policy/CHANGELOG.md`
6. **Open PR**; CODEOWNERS approval required (`@ThermoclineLeviathan`); when team grows, dual-review on `keys/` paths
7. **Submit AEGIS Stage-2 self-eval** before merge (key rotation = AEGIS-self-tune class per §5; expect Josh-explicit-✅ override)
8. **Coordinate consumer-repo SHA pin updates** in their next routine PRs
9. **Rollover-window**: previous keys remain valid for `ttl_per_risk_class` of currently-issued attestations (24h max); after rollover window, server stops issuing under old keys

## Why not TUF (sigstore-style)?

Cosign-style TUF distribution with threshold signatures + delegated metadata is **overkill for v1**. Sigstore needs TUF because Fulcio short-lived certs rotate constantly + require global trust. AEGIS attestation keys are stable long-lived service keys — Git-versioned PEM with PR-gated CODEOWNERS rotation is sufficient. TUF can be added in Phase-2 ecosystem-compat work (post-Sprint 7) if external integrators require it.

## Reporting key-compromise suspicions

Email `security@undercurrentholdings.com` immediately + open a private vulnerability report on GitHub. **Do NOT open a public issue or PR mentioning suspected compromise.**
