"""Check fingerprint parity between key bytes and policy/verifier-policy-v1.yaml.

The aegis-policy trust spine consists of:
  - `keys/ed25519-public.pem` — 113B PEM-wrapped 32B Ed25519 public
  - `keys/mldsa65-public.bin` — 1952B raw ML-DSA-65 public
  - `policy/verifier-policy-v1.yaml required_keyids` — SHA-256 hex over each
    key's RAW bytes (NOT the PEM wrapper for Ed25519)

This gate enforces that the SHA-256 fingerprints declared in
`required_keyids` exactly match what the key bytes hash to. If a future PR
edits either side without matching the other, this script fails-loud
(exit 1) — preventing the "single-char fingerprint typo causes live deploy
outage" failure mode (cosmic-flute §28.5 box 7 + §30 §3.1).

Counterpart of `scripts/check_error_class_parity.py` (which guards the
taxonomy invariant between the SDK and the policy `fail_closed_on` list).
Same exit codes; same one-error-per-line output convention.

Closes the manual-audit gap that pre-merge audit cycles relied on humans
to perform. Sprint 5/E1.5 Phase 5 C5 implementation per cosmic-flute §30 §3.1.

Usage:
    pip install pyyaml cryptography
    python scripts/check_fingerprints.py

Exit codes:
    0 — both fingerprints match the bytes they reference
    1 — at least one mismatch (output names which key + shows got/want)
    2 — execution error (file missing, PEM unparseable, yaml malformed, etc.)
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml
from cryptography.hazmat.primitives import serialization

REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY_FILE = REPO_ROOT / "policy" / "verifier-policy-v1.yaml"
ED25519_KEY_FILE = REPO_ROOT / "keys" / "ed25519-public.pem"
MLDSA65_KEY_FILE = REPO_ROOT / "keys" / "mldsa65-public.bin"


def _sha256_hex(data: bytes) -> str:
    """Return lowercase 64-char SHA-256 hex of `data`."""
    return hashlib.sha256(data).hexdigest()


def _load_ed25519_raw(pem_path: Path) -> bytes:
    """Load a PEM-wrapped Ed25519 public key + return its 32-byte raw form.

    The `cryptography` library understands Ed25519 X.509 SubjectPublicKeyInfo
    natively (unlike ML-DSA-65 — see `scripts/extract_mldsa65_raw.py` for the
    manual ASN.1 parse workaround there).
    """
    key = serialization.load_pem_public_key(pem_path.read_bytes())
    return key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _load_policy_keyids(policy_path: Path) -> dict[str, str]:
    """Load `required_keyids` block from the policy YAML."""
    with policy_path.open() as fp:
        policy = yaml.safe_load(fp)
    keyids = policy.get("required_keyids")
    if not isinstance(keyids, dict):
        raise ValueError(
            f"{policy_path.name}: missing or malformed required_keyids block"
        )
    return keyids


def main() -> int:
    # Load expected fingerprints from the policy file
    try:
        keyids = _load_policy_keyids(POLICY_FILE)
    except (OSError, yaml.YAMLError, ValueError) as e:
        print(f"ERROR loading policy: {e}", file=sys.stderr)
        return 2

    expected_ed25519 = keyids.get("ed25519")
    expected_mldsa65 = keyids.get("mldsa65")
    if not isinstance(expected_ed25519, str) or not isinstance(expected_mldsa65, str):
        print(
            "ERROR: required_keyids must contain string `ed25519` and `mldsa65` fields",
            file=sys.stderr,
        )
        return 2
    # Normalize expected values to lowercase + stripped (hashlib.hexdigest
    # always returns lowercase). Catches case-mixed YAML edits without
    # confusing "f4e6 vs F4E6" diagnostics.
    expected_ed25519 = expected_ed25519.strip().lower()
    expected_mldsa65 = expected_mldsa65.strip().lower()

    # Compute actual fingerprints over the committed bytes
    try:
        ed25519_raw = _load_ed25519_raw(ED25519_KEY_FILE)
        mldsa65_raw = MLDSA65_KEY_FILE.read_bytes()
    except (OSError, ValueError) as e:
        print(f"ERROR reading key files: {e}", file=sys.stderr)
        return 2

    # Defense-in-depth size invariants (FIPS 204 + Ed25519 RFC 8032). Catches
    # truncated/padded files with a clear error before they propagate to a
    # confusing fingerprint mismatch downstream.
    if len(ed25519_raw) != 32:
        print(
            f"ERROR: keys/ed25519-public.pem extracted to {len(ed25519_raw)}B; "
            f"expected exactly 32B (Ed25519 raw public-key size per RFC 8032)",
            file=sys.stderr,
        )
        return 2
    if len(mldsa65_raw) != 1952:
        print(
            f"ERROR: keys/mldsa65-public.bin is {len(mldsa65_raw)}B; "
            f"expected exactly 1952B (ML-DSA-65 raw public-key size per FIPS 204 Table 2)",
            file=sys.stderr,
        )
        return 2

    actual_ed25519 = _sha256_hex(ed25519_raw)
    actual_mldsa65 = _sha256_hex(mldsa65_raw)

    mismatches = []
    if actual_ed25519 != expected_ed25519:
        mismatches.append(
            f"  ed25519:\n"
            f"    bytes_sha256 ({ED25519_KEY_FILE.name}): {actual_ed25519}\n"
            f"    policy_value  (required_keyids.ed25519):  {expected_ed25519}"
        )
    if actual_mldsa65 != expected_mldsa65:
        mismatches.append(
            f"  mldsa65:\n"
            f"    bytes_sha256 ({MLDSA65_KEY_FILE.name}): {actual_mldsa65}\n"
            f"    policy_value  (required_keyids.mldsa65):  {expected_mldsa65}"
        )

    if mismatches:
        print(
            "✗ FINGERPRINT PARITY VIOLATED — policy/verifier-policy-v1.yaml\n"
            "  required_keyids does NOT match the SHA-256 of the bytes in\n"
            "  keys/. This is a trust-spine integrity break.\n",
            file=sys.stderr,
        )
        for m in mismatches:
            print(m, file=sys.stderr)
        print(
            "\n"
            "Likely causes:\n"
            "  (a) someone edited required_keyids without re-fetching key bytes\n"
            "  (b) someone replaced keys/*.{pem,bin} without recomputing fingerprints\n"
            "  (c) typo in the hex string (single-char drift)\n"
            "\n"
            "Fix: re-extract raw bytes + recompute SHA-256, OR revert one side\n"
            "to match the other. See docs/key-rotation-runbook.md for the\n"
            "canonical rotation procedure.",
            file=sys.stderr,
        )
        return 1

    print(
        f"✓ FINGERPRINT PARITY HOLDS 2-vs-2 — policy/verifier-policy-v1.yaml\n"
        f"  required_keyids match SHA-256 over keys/ bytes.\n"
        f"  ed25519: {actual_ed25519}\n"
        f"  mldsa65: {actual_mldsa65}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
