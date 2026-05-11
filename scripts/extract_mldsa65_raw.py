#!/usr/bin/env python3
"""Extract raw 1952-byte ML-DSA-65 public key from a GCP KMS PEM file.

Per cosmic-flute §28.16.6 + §28.17 Phase 1 execution: GCP KMS's
`get_public_key` for `PQ_SIGN_ML_DSA_65` returns an X.509 SubjectPublicKeyInfo
PEM (2,726 bytes) using ML-DSA OID `2.16.840.1.101.3.4.3.18`. The widely-deployed
Python `cryptography` library (≤44.x as of 2026-05-10) does NOT recognize this
OID, so `serialization.load_pem_public_key()` raises
`UnsupportedAlgorithm`.

Workaround: manually ASN.1-DER parse the PEM. After base64-decoding the PEM
body to DER bytes, scan for the BIT STRING marker `0x03 0x82` with length 1953
(1952 raw + 1 unused-bits byte). The raw 1952B starts at offset+5 from the
marker (1 byte tag + 3 bytes length + 1 byte unused-bits-count = 5).

This algorithm is the source-of-truth canonical mechanism for converting
GCP KMS ML-DSA-65 PEM output into the raw bytes that:
  - `keys/mldsa65-public.bin` stores (1952B raw)
  - `policy/verifier-policy-v1.yaml required_keyids.mldsa65` references
    (SHA-256 hex over those 1952B)
  - the SDK `verify_attestation_locally` consumes
    (`AttestationVerifyKey.mldsa65_public` field, 1952B)

Cross-references:
  - Upstream ADR-012 (algorithm migration; aegis-governance@7e422b2)
  - ADR-002 (key ceremony log; this repo)
  - ADR-003 (algorithm migration vendoring; this repo)
  - cosmic-flute §28.17 (Phase 1 ceremony execution + this algorithm proven)

Usage:
    python3 scripts/extract_mldsa65_raw.py <input.pem> <output.bin>

Exits 0 on success; non-zero with a diagnostic on any parse failure.
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path


MLDSA65_RAW_LEN = 1952  # FIPS 204 ML-DSA-65 public-key size
BIT_STRING_TAG = 0x03  # ASN.1 BIT STRING tag
LENGTH_LONG_FORM_2BYTES = 0x82  # Long-form length: next 2 bytes encode length
WRAPPED_LEN = MLDSA65_RAW_LEN + 1  # +1 for the unused-bits-count byte
WRAPPED_LEN_HI = (WRAPPED_LEN >> 8) & 0xFF
WRAPPED_LEN_LO = WRAPPED_LEN & 0xFF

# DER encoding of OID 2.16.840.1.101.3.4.3.18 (id-ml-dsa-65 per NIST CSOR + FIPS 204):
#   tag=06 (OID), length=09, value=60 86 48 01 65 03 04 03 12 (9 bytes)
# This appears in the AlgorithmIdentifier inside the X.509 SubjectPublicKeyInfo
# BEFORE the BIT STRING that wraps the raw 1952B public key. Anchoring on the OID
# first eliminates false BIT STRING matches earlier in the DER (defense-in-depth
# against future GCP KMS PEM format changes that may embed length-1953 patterns
# in unrelated structures, OR maliciously-crafted PEMs containing collision bytes).
ML_DSA_65_OID_DER = bytes(
    [0x06, 0x09, 0x60, 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x03, 0x12]
)


def extract_raw(pem_bytes: bytes) -> bytes:
    """Parse a PEM-wrapped X.509 SubjectPublicKeyInfo + return 1952B raw."""
    pem_text = pem_bytes.decode("ascii")
    body_match = re.search(
        r"-----BEGIN PUBLIC KEY-----\s*(.*?)\s*-----END PUBLIC KEY-----",
        pem_text,
        re.DOTALL,
    )
    if not body_match:
        raise ValueError("Input is not a valid PEM-wrapped PUBLIC KEY block")
    der = base64.b64decode(body_match.group(1).replace("\n", "").replace("\r", ""))

    # Anchor 1: locate ML-DSA-65 OID inside the AlgorithmIdentifier. Refuses
    # to extract from any non-ML-DSA-65 input even if it happens to contain
    # the BIT STRING length pattern.
    oid_idx = der.find(ML_DSA_65_OID_DER)
    if oid_idx < 0:
        raise ValueError(
            f"DER does not contain ML-DSA-65 OID {ML_DSA_65_OID_DER.hex()} "
            f"(algorithm is NOT ML-DSA-65, or PEM is not a "
            f"SubjectPublicKeyInfo)"
        )

    # Anchor 2: BIT STRING with length 1953 must appear AFTER the OID
    # (per X.509 SPKI structure: AlgorithmIdentifier(OID) precedes
    # subjectPublicKey(BIT STRING)). Searching from oid_idx prevents matching
    # any earlier coincidental byte sequence in the DER.
    marker = bytes(
        [BIT_STRING_TAG, LENGTH_LONG_FORM_2BYTES, WRAPPED_LEN_HI, WRAPPED_LEN_LO]
    )
    idx = der.find(marker, oid_idx)
    if idx < 0:
        raise ValueError(
            f"DER contains ML-DSA-65 OID but no length-1953 BIT STRING "
            f"after it (marker {marker.hex()}); PEM structure unexpected"
        )

    # Anchor 3 (uniqueness): no second BIT-STRING-1953 marker may exist later
    # in the DER. Multiple matches signal an ambiguous parse — refuse rather
    # than guess which one wraps the public key.
    second_idx = der.find(marker, idx + 1)
    if second_idx >= 0:
        raise ValueError(
            f"DER contains MULTIPLE BIT STRING markers {marker.hex()} "
            f"(at offsets {idx} and {second_idx}); ambiguous extraction "
            f"refused. PEM may be malformed or attacker-crafted."
        )

    # marker is 4 bytes; +1 for unused-bits-count byte (always 0 for byte-aligned keys)
    raw_start = idx + 5
    raw = der[raw_start : raw_start + MLDSA65_RAW_LEN]
    if len(raw) != MLDSA65_RAW_LEN:
        raise ValueError(
            f"Extracted {len(raw)} bytes; expected exactly {MLDSA65_RAW_LEN}"
        )
    return raw


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <input.pem> <output.bin>", file=sys.stderr)
        return 2
    pem_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    try:
        raw = extract_raw(pem_path.read_bytes())
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    out_path.write_bytes(raw)
    print(f"✓ extracted {len(raw)} bytes from {pem_path} → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
