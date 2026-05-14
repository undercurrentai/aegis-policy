"""One-shot offline generator for Sprint 5/E2 self-test fixtures.

Produces under `tests/fixtures/`:

    test-keys/
      ed25519-public.pem    — 113B PEM-wrapped 32B Ed25519 public (ephemeral)
      mldsa65-public.bin    — 1952B raw ML-DSA-65 public (ephemeral)
    policy-test-v1.yaml     — mirror of production policy/verifier-policy-v1.yaml
                              but with `required_keyids` set to SHA-256 over the
                              ephemeral test keys above
    envelope-valid-preview.json
                            — DSSE envelope with valid sigs, environment=preview,
                              risk_class=low, expires_at = 2099-01-01 (far future)
    envelope-tampered-digest.json
                            — same as -valid but with subject[0].digest.sha256
                              mutated by one character (still valid hex), so
                              the verifier emits AttestationDigestMismatch
                              against the -valid digest. Signatures over the
                              ORIGINAL canonical bytes still verify; the
                              mismatch is detected by the digest comparison.
    envelope-expired.json   — same as -valid but expires_at = 2024-01-01 (past)

The test envelopes are signed with the EPHEMERAL test keys, NOT the production
keys committed under `keys/`. This means:

  - The self-test workflow MUST set `AEGIS_KEYS_DIR_OVERRIDE=tests/fixtures/test-keys`
    and `AEGIS_POLICY_PATH_OVERRIDE=tests/fixtures/policy-test-v1.yaml`
    to make verify_action.py load the matching test keys + policy.
  - Production envelopes from aegis-governance Cloud Run will NEVER verify
    against these test keys, and vice versa. Total isolation.

Cosmic-flute §34.7 + §34.14 G + §34.14 L. Closes Sprint 5/E2 Phase D fixtures.

Re-run when:
  - SDK wire-format changes (e.g., new required predicate field)
  - Algorithm migration (rare; would need a separate test-key ceremony)
  - You want to regenerate test keys (any time; fixtures are not load-bearing
    for production trust — they're isolated entirely from real KMS keys)

Usage:
    cd aegis-policy
    pip install pyyaml cryptography liboqs-python rfc8785
    python tests/fixtures/generate_fixtures.py

Idempotency: overwrites all generated files unconditionally. Safe to run
repeatedly. The `subject_name` field is tagged "e2-selftest-fixture-2026-05-13"
for findability if any of these fixtures ever leak into production audit logs.
"""

from __future__ import annotations

import base64
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

import oqs
import rfc8785
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

FIXTURES_DIR = Path(__file__).resolve().parent
REPO_ROOT = FIXTURES_DIR.parent.parent
TEST_KEYS_DIR = FIXTURES_DIR / "test-keys"
TEST_POLICY_FILE = FIXTURES_DIR / "policy-test-v1.yaml"
PROD_POLICY_FILE = REPO_ROOT / "policy" / "verifier-policy-v1.yaml"

# Must match production server's CONTEXT_STRING byte-exactly. The verifier in
# aegis-sdk[verify] computes H(CONTEXT_STRING || PAE) and verifies that hash
# under the public key, so signers MUST sign over the SAME hash.
CONTEXT_STRING = b"aegis-attestation-v1"

PAYLOAD_TYPE = "application/vnd.in-toto+json"


def _nfc_normalize_strings(value: Any) -> Any:
    """Recursively NFC-normalize all strings in a JSON-able structure.

    Mirrors `aegis-sdk/src/aegis/_verify_local.py::_nfc_normalize_strings` so
    the canonical bytes the verifier reconstructs match the bytes the signer
    canonicalized. Without this, Unicode-decomposed strings in the input would
    drift across the signer/verifier boundary.
    """
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {_nfc_normalize_strings(k): _nfc_normalize_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_nfc_normalize_strings(v) for v in value]
    return value


def _canonicalize_statement(statement_dict: dict[str, Any]) -> bytes:
    """NFC-normalize, then RFC 8785 canonicalize."""
    normalized = _nfc_normalize_strings(statement_dict)
    return rfc8785.dumps(normalized)


def _build_dsse_pae(payload_type: str, body: bytes) -> bytes:
    """Construct DSSE Pre-Authentication Encoding per the in-toto spec.

    Mirrors `aegis-sdk/src/aegis/_verify_local.py::_build_dsse_pae` byte-for-
    byte. The format is:
        DSSEv1 <len(type)> <type> <len(body)> <body>
    """
    type_bytes = payload_type.encode("ascii")
    return (
        b"DSSEv1 "
        + str(len(type_bytes)).encode("ascii") + b" " + type_bytes
        + b" "
        + str(len(body)).encode("ascii") + b" " + body
    )


def _generate_ed25519_keypair() -> tuple[Ed25519PrivateKey, bytes, bytes]:
    """Generate ephemeral Ed25519 keypair. Returns (private, public_raw_32B, public_pem_113B)."""
    private_key = Ed25519PrivateKey.generate()
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_raw, public_pem


def _sign_ed25519_with_context(
    private_key: Ed25519PrivateKey, pae: bytes
) -> bytes:
    """Sign H(CONTEXT_STRING || PAE) with Ed25519. Mirrors verifier expectation."""
    msg_hash = hashlib.sha256(CONTEXT_STRING + pae).digest()
    return private_key.sign(msg_hash)


def _sign_mldsa65_with_context(signer: Any, pae: bytes) -> bytes:
    """Sign H(CONTEXT_STRING || PAE) with ML-DSA-65 using prefix-hash-and-sign.

    Per upstream ADR-012 §"Context-string binding under KMS": GCP KMS
    asymmetric_sign API does NOT expose a FIPS 204 ctx-string parameter;
    AEGIS uses uniform prefix-hash-and-sign for BOTH algorithms.
    """
    msg_hash = hashlib.sha256(CONTEXT_STRING + pae).digest()
    return signer.sign(msg_hash)


def _build_envelope(
    statement: dict[str, Any],
    ed25519_private: Ed25519PrivateKey,
    mldsa65_signer: Any,
    ed25519_keyid: str,
    mldsa65_keyid: str,
) -> dict[str, Any]:
    """Construct a DSSE envelope: canonicalize statement → PAE → sign → assemble."""
    canonical = _canonicalize_statement(statement)
    pae = _build_dsse_pae(PAYLOAD_TYPE, canonical)

    ed_sig = _sign_ed25519_with_context(ed25519_private, pae)
    ml_sig = _sign_mldsa65_with_context(mldsa65_signer, pae)

    payload_b64 = base64.b64encode(canonical).decode("ascii")
    ed_sig_b64 = base64.b64encode(ed_sig).decode("ascii")
    ml_sig_b64 = base64.b64encode(ml_sig).decode("ascii")

    return {
        # camelCase key per in-toto + DSSE v1 canonical JSON wire format
        # (matches aegis-sdk DSSEEnvelope.to_dict + from_response which both
        # read/write "payloadType"; serialized envelopes published by the
        # AEGIS API use this form). Using "payload_type" snake_case here
        # was hidden by SDK's default-fallback in from_response and would
        # produce a false-positive happy path for fixtures that genuinely
        # need to exercise the wire-format contract. /quality-gate Phase 2
        # cycle 1 remediation of Lane B Agent 1 F1.
        "payloadType": PAYLOAD_TYPE,
        "payload": payload_b64,
        "signatures": [
            {"keyid": ed25519_keyid, "sig": ed_sig_b64},
            {"keyid": mldsa65_keyid, "sig": ml_sig_b64},
        ],
    }


def _make_statement(
    *,
    decision_id: str,
    artifact_digest: str,
    environment: str,
    risk_class: str,
    policy_version: str,
    expires_at: str,
    subject_name: str = "e2-selftest-fixture-2026-05-13",
) -> dict[str, Any]:
    """Build an in-toto Statement v1 wrapping an AEGIS predicate."""
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": subject_name,
                "digest": {"sha256": artifact_digest},
            }
        ],
        "predicateType": "https://aegis.undercurrentholdings.com/attestation/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://aegis.undercurrentholdings.com/buildtype/selftest/v1",
                "externalParameters": {
                    "repository": "undercurrentai/aegis-policy",
                    "workflow_ref": "tests/fixtures/generate_fixtures.py",
                },
            },
            "runDetails": {
                "builder": {
                    "id": "https://github.com/undercurrentai/aegis-policy/tests/fixtures",
                },
                "metadata": {
                    "invocationId": "selftest-fixture-generator",
                },
            },
            "governance": {
                "decision_id": decision_id,
                "artifact_digest": artifact_digest,
                "environment": environment,
                "risk_class": risk_class,
                "policy_version": policy_version,
                "issued_at": "2026-05-13T00:00:00+00:00",
                "expires_at": expires_at,
                "gate_pass_states": {
                    "risk": "pass",
                    "profit": "pass",
                    "novelty": "pass",
                    "complexity": "pass",
                    "quality": "pass",
                    "utility": "pass",
                },
                "repository": "undercurrentai/aegis-policy",
                "workflow_ref": "tests/fixtures/generate_fixtures.py",
                "run_id": "selftest-2026-05-13",
                "run_attempt": 1,
            },
        },
    }


def main() -> int:
    # ─────────────────────────────────────────────────────────────────────────
    # 1. Generate ephemeral keys
    # ─────────────────────────────────────────────────────────────────────────
    print("Generating ephemeral Ed25519 keypair...")
    ed25519_private, ed25519_public_raw, ed25519_public_pem = _generate_ed25519_keypair()
    ed25519_fingerprint = hashlib.sha256(ed25519_public_raw).hexdigest()
    print(f"  Ed25519 SHA-256: {ed25519_fingerprint}")

    print("Generating ephemeral ML-DSA-65 keypair...")
    # Use a context manager so the signer is alive for all 3 envelopes
    with oqs.Signature("ML-DSA-65") as mldsa65_signer:
        mldsa65_public_raw = mldsa65_signer.generate_keypair()
        mldsa65_fingerprint = hashlib.sha256(mldsa65_public_raw).hexdigest()
        print(f"  ML-DSA-65 SHA-256: {mldsa65_fingerprint}")

        # ─────────────────────────────────────────────────────────────────────
        # 2. Write test-keys/
        # ─────────────────────────────────────────────────────────────────────
        TEST_KEYS_DIR.mkdir(parents=True, exist_ok=True)
        (TEST_KEYS_DIR / "ed25519-public.pem").write_bytes(ed25519_public_pem)
        (TEST_KEYS_DIR / "mldsa65-public.bin").write_bytes(mldsa65_public_raw)
        print(f"  Wrote {TEST_KEYS_DIR / 'ed25519-public.pem'} ({len(ed25519_public_pem)}B)")
        print(f"  Wrote {TEST_KEYS_DIR / 'mldsa65-public.bin'} ({len(mldsa65_public_raw)}B)")

        # ─────────────────────────────────────────────────────────────────────
        # 3. Build test policy-test-v1.yaml (mirror prod policy but with test fingerprints)
        # ─────────────────────────────────────────────────────────────────────
        with PROD_POLICY_FILE.open() as fp:
            prod_policy = yaml.safe_load(fp)
        test_policy = dict(prod_policy)
        test_policy["required_keyids"] = {
            "ed25519": ed25519_fingerprint,
            "mldsa65": mldsa65_fingerprint,
        }
        # Strip the leading comment block in the test policy header for clarity
        TEST_POLICY_FILE.write_text(
            "# AEGIS Verifier Policy v1 — TEST POLICY for Sprint 5/E2 self-test fixtures.\n"
            "# Generated by tests/fixtures/generate_fixtures.py.\n"
            "# Mirrors production policy/verifier-policy-v1.yaml but with EPHEMERAL\n"
            "# test-key fingerprints under required_keyids. Loaded only when\n"
            "# AEGIS_POLICY_PATH_OVERRIDE points here (self-test workflow only).\n"
            "\n"
            + yaml.safe_dump(test_policy, sort_keys=False, default_flow_style=False)
        )
        print(f"  Wrote {TEST_POLICY_FILE}")

        # ─────────────────────────────────────────────────────────────────────
        # 4. Define keyid identifiers (must use prefixes that aegis-sdk recognizes)
        # ─────────────────────────────────────────────────────────────────────
        ed25519_keyid = f"ed25519:{ed25519_fingerprint[:16]}"
        mldsa65_keyid = f"ml-dsa-65:{mldsa65_fingerprint[:16]}"

        # ─────────────────────────────────────────────────────────────────────
        # 5. Build envelope-valid-preview.json
        # ─────────────────────────────────────────────────────────────────────
        # Pick an artifact digest (SHA-256 of a deterministic fixture string).
        # Real consumers compute this over their actual build artifact.
        VALID_DIGEST = hashlib.sha256(b"sprint-5-e2-selftest-valid-2026-05-13").hexdigest()
        valid_statement = _make_statement(
            decision_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            artifact_digest=VALID_DIGEST,
            environment="preview",
            risk_class="low",
            policy_version=str(test_policy["policy_version"]),  # 2.1.0 (matches test policy)
            expires_at="2099-01-01T00:00:00+00:00",
        )
        valid_envelope = _build_envelope(
            valid_statement, ed25519_private, mldsa65_signer, ed25519_keyid, mldsa65_keyid
        )
        valid_path = FIXTURES_DIR / "envelope-valid-preview.json"
        valid_path.write_text(json.dumps(valid_envelope, indent=2) + "\n")
        print(f"  Wrote {valid_path} (digest={VALID_DIGEST})")

        # ─────────────────────────────────────────────────────────────────────
        # 6. Build envelope-tampered-digest.json
        # ─────────────────────────────────────────────────────────────────────
        # The KEY insight: this fixture has VALID signatures over the canonical
        # bytes of the ORIGINAL statement (with the ORIGINAL digest). The
        # consumer of this fixture will pass `expected-digest=<tampered>` to
        # the action. The action's verifier-layer:
        #   - re-derives canonical bytes from envelope.payload → matches original
        #   - verifies Ed25519 + ML-DSA-65 over PAE(canonical) → matches (sigs valid)
        #   - reads subject[0].digest.sha256 from envelope → matches original
        #   - compares to expected_digest input → MISMATCH → AttestationDigestMismatch
        # So this fixture IS the envelope-valid-preview.json verbatim; the
        # "tamper" is in the EXPECTED_DIGEST input the test passes, not in the
        # envelope bytes. Naming it -tampered-digest.json reflects the intent
        # of the test case, not a modification of the envelope itself.
        #
        # An alternative (mutating subject.digest INSIDE the envelope after
        # signing) would fail with AttestationCanonicalBytesMismatch because
        # the verifier re-canonicalizes the payload + compares to the input
        # bytes; mutation would invalidate the canonical bytes invariant
        # first. We pick the cleaner test case here.
        tampered_path = FIXTURES_DIR / "envelope-tampered-digest.json"
        tampered_path.write_text(json.dumps(valid_envelope, indent=2) + "\n")
        print(f"  Wrote {tampered_path} (uses same envelope; tests pass MISMATCHED expected-digest)")

        # The "expected-digest" the self-test workflow passes to trigger
        # AttestationDigestMismatch is captured here for the workflow + tests
        # to import.
        TAMPERED_EXPECTED_DIGEST = (
            "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        )

        # ─────────────────────────────────────────────────────────────────────
        # 7. Build envelope-expired.json
        # ─────────────────────────────────────────────────────────────────────
        EXPIRED_DIGEST = hashlib.sha256(b"sprint-5-e2-selftest-expired-2026-05-13").hexdigest()
        expired_statement = _make_statement(
            decision_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            artifact_digest=EXPIRED_DIGEST,
            environment="preview",
            risk_class="low",
            policy_version=str(test_policy["policy_version"]),
            expires_at="2024-01-01T00:00:00+00:00",  # past
        )
        expired_envelope = _build_envelope(
            expired_statement,
            ed25519_private,
            mldsa65_signer,
            ed25519_keyid,
            mldsa65_keyid,
        )
        expired_path = FIXTURES_DIR / "envelope-expired.json"
        expired_path.write_text(json.dumps(expired_envelope, indent=2) + "\n")
        print(f"  Wrote {expired_path} (digest={EXPIRED_DIGEST})")

    # ─────────────────────────────────────────────────────────────────────────
    # 8. Manifest with the digests + decision_ids the tests should reference
    # ─────────────────────────────────────────────────────────────────────────
    manifest = {
        "generated_by": "tests/fixtures/generate_fixtures.py",
        "fingerprints": {
            "ed25519": ed25519_fingerprint,
            "mldsa65": mldsa65_fingerprint,
        },
        "keyids": {
            "ed25519": ed25519_keyid,
            "mldsa65": mldsa65_keyid,
        },
        "envelope_valid_preview": {
            "path": "envelope-valid-preview.json",
            "decision_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "artifact_digest": VALID_DIGEST,
            "environment": "preview",
            "policy_version": str(test_policy["policy_version"]),
        },
        "envelope_tampered_digest": {
            "path": "envelope-tampered-digest.json",
            "decision_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "original_artifact_digest": VALID_DIGEST,
            "tampered_expected_digest": TAMPERED_EXPECTED_DIGEST,
            "environment": "preview",
            "policy_version": str(test_policy["policy_version"]),
        },
        "envelope_expired": {
            "path": "envelope-expired.json",
            "decision_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "artifact_digest": EXPIRED_DIGEST,
            "environment": "preview",
            "policy_version": str(test_policy["policy_version"]),
        },
    }
    (FIXTURES_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  Wrote {FIXTURES_DIR / 'manifest.json'}")

    print("\nFixture generation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
