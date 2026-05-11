# Trust Roots — Canonical AEGIS Attestation Public Keys

This directory contains the canonical Ed25519 + ML-DSA-65 public keys that consumers use to verify AEGIS attestations. Keys committed 2026-05-10 (KMS-derived; SOFTWARE protection per [ADR-002](../docs/architecture/adr/ADR-002-key-ceremony-2026-05-10.md)).

## Files

| File | Format | Size | Purpose |
|---|---|---|---|
| `ed25519-public.pem` | PEM-wrapped raw Ed25519 public key | 32B raw / 113B PEM | Consumer pins via SHA-256 fingerprint; E2 verifier kit reads via `cryptography.hazmat.primitives.serialization.load_pem_public_key` |
| `mldsa65-public.bin` | Raw ML-DSA-65 public key (no standard PEM yet) | 1952B raw | Consumer pins via SHA-256 fingerprint; E2 verifier kit reads via `oqs.Signature("ML-DSA-65")` (`liboqs-python>=0.14.1`) |

**SHA-256 fingerprints** (verified by the `fingerprint-parity.yml` CI gate on every PR):

- ed25519: `33378f58b12a92488fd57888323b77fef2ffd9bd051c10768fc770c02025d97d`
- mldsa65: `f4e65bb77a508e82cd60b576075866d3e6447f4d3fd841ef1c3f1b93ecbe7d93`

These match the SHA-256 of the RAW bytes (32B Ed25519 extracted via `cryptography.serialization`; 1952B ML-DSA-65 stored unwrapped). The fingerprints are also referenced in `policy/verifier-policy-v1.yaml required_keyids`.

## Why two different formats?

- **Ed25519** has standard PEM encoding (RFC 8410) supported by `cryptography`, `openssl`, OpenSSH, etc. PEM is the obvious choice — tooling-friendly + auditable.
- **ML-DSA-65** is a NIST FIPS 204 final post-quantum scheme. As of 2026-05-10, **the widely-deployed Python `cryptography` library (≤44.x) does NOT yet recognize ML-DSA OID `2.16.840.1.101.3.4.3.18`** (NIST CSOR `id-ml-dsa-65`; FIPS 204 §4 / Table 2) — `serialization.load_pem_public_key()` raises `UnsupportedAlgorithm` on the X.509 SubjectPublicKeyInfo PEM that GCP KMS returns. We commit raw 1952-byte material as `.bin` to sidestep this entirely. The raw format matches what `oqs.Signature("ML-DSA-65").verify(...)` expects directly. See [`../scripts/extract_mldsa65_raw.py`](../scripts/extract_mldsa65_raw.py) for the ASN.1 DER extraction algorithm (used at key-rotation time to convert KMS's PEM output to raw).

## Pinning model

Per cosmic-flute §17 Critical 3 + ADR-011 §Negative §6 mitigations: consumers pin this repo by **immutable commit SHA**, never by `@main`. The E2 composite GitHub Action (Sprint 5/E2) will:

1. Resolve the pinned SHA via `actions/checkout`
2. Read both key files from `keys/`
3. Compute SHA-256 fingerprint of each (Ed25519: extract raw via `cryptography`; ML-DSA-65: read raw directly)
4. Compare against caller-supplied action inputs OR `policy/verifier-policy-v1.yaml required_keyids` at the pinned SHA
5. Pass keys to the verifier script (`scripts/verify.py` in E2)

This dual-pinning (SHA on the repo + SHA-256 on the keys) makes silent key-substitution impossible: an attacker would need to (a) push to this repo (CODEOWNERS-protected; org-Ruleset-enforced in Sprint 5/E1.5 Phase 7) AND (b) update the consumer's pinned SHA (still requires consumer-repo CODEOWNERS approval).

The `fingerprint-parity.yml` workflow ([added Phase 5 C5](../.github/workflows/fingerprint-parity.yml)) enforces the second invariant locally: bytes in `keys/` must hash to the values in `policy/verifier-policy-v1.yaml required_keyids` on every PR.

## Rotation procedure

See [`../docs/key-rotation-runbook.md`](../docs/key-rotation-runbook.md). Cross-references:

- **ADR-001** — Repo trust model (why CODEOWNERS + SHA-pinning are load-bearing)
- **ADR-002** — Sprint 5/E1.5 key ceremony (initial provenance; SOFTWARE-protection acceptance)
- **ADR-003** — ML-DSA-44 → ML-DSA-65 algorithm migration (why these specific bytes + sizes)
- Upstream **ADR-011** (artifact-bound attestations; N4 distinct-keys invariant) + **ADR-012** (algorithm migration + uniform prefix-hash-and-sign under KMS) — at `aegis-governance@7e422b2`

## Why not TUF (sigstore-style)?

Cosign-style TUF distribution with threshold signatures + delegated metadata is **overkill for v1**. Sigstore needs TUF because Fulcio short-lived certs rotate constantly + require global trust. AEGIS attestation keys are stable long-lived service keys — Git-versioned PEM/BIN with PR-gated CODEOWNERS rotation is sufficient. The fingerprint-parity gate catches the most-likely failure mode (single-char typo) without adding ceremony overhead. TUF can be added in Phase-2 ecosystem-compat work (post-Sprint 7) if external integrators require it.

## Reporting key-compromise suspicions

Email `security@undercurrentholdings.com` immediately + open a private vulnerability report on GitHub. **Do NOT open a public issue or PR mentioning suspected compromise.**
