"""Offline cryptographic verification of AEGIS attestation envelopes (Sprint 4 / D2).

Pure crypto — NO HTTP. Consumers pin public keys at SDK init; verification runs
entirely locally. Mirrors server-side ``AttestationProvider.verify()`` byte-for-byte
to guarantee identical cryptographic outcomes between offline + server verification.

Available only when the ``[verify]`` extra is installed::

    pip install aegis-governance[verify]

Adds runtime deps: ``cryptography``, ``liboqs-python``, ``rfc8785``.

Usage::

    from aegis import verify_attestation_locally, AttestationVerifyKey

    keys = AttestationVerifyKey(
        ed25519_public=b"...32 bytes...",
        mldsa44_public=b"...1312 bytes...",
    )

    valid, error_class = verify_attestation_locally(
        envelope=envelope,
        expected_digest="<sha256 lowercase hex 64>",
        expected_environment="production",
        keys=keys,
    )
    if not valid:
        raise RuntimeError(f"local verification failed: {error_class}")

The error_class strings emitted exactly match the server-side
``AttestationProvider.verify()`` strings, so consumer code can check
``error_class`` identically across HTTP-verify (D1) and offline-verify (D2).
"""

from __future__ import annotations

import base64
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import oqs  # type: ignore[import-untyped]
import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aegis.types import DSSEEnvelope, InTotoStatement

# ── Constants (must match server src/crypto/attestation_provider.py) ───────────

CONTEXT_STRING: bytes = b"aegis-attestation-v1"
PAYLOAD_TYPE: str = "application/vnd.in-toto+json"
ED25519_KEYID_PREFIX: str = "ed25519:"
MLDSA_KEYID_PREFIX: str = "ml-dsa-44:"
ED25519_PUBLIC_LEN: int = 32
MLDSA44_PUBLIC_LEN: int = 1312


@dataclass(frozen=True)
class AttestationVerifyKey:
    """Pinned public-key material for offline AEGIS attestation verification.

    Consumers fetch keys out-of-band (Sprint 5/E2 verifier-kit ships canonical
    keys; or fetch from a project KMS / config) and construct this dataclass
    once at SDK init. The same keys are used for all subsequent verifications.

    Args:
        ed25519_public: Raw 32-byte Ed25519 public key.
        mldsa44_public: Raw 1312-byte ML-DSA-44 public key.

    Raises:
        ValueError: if either key length doesn't match the expected size.
    """

    ed25519_public: bytes
    mldsa44_public: bytes

    def __post_init__(self) -> None:
        if len(self.ed25519_public) != ED25519_PUBLIC_LEN:
            raise ValueError(
                f"ed25519_public must be {ED25519_PUBLIC_LEN} bytes, got {len(self.ed25519_public)}"
            )
        if len(self.mldsa44_public) != MLDSA44_PUBLIC_LEN:
            raise ValueError(
                f"mldsa44_public must be {MLDSA44_PUBLIC_LEN} bytes, got {len(self.mldsa44_public)}"
            )


# ── DSSE PAE (must match server attestation_provider.py byte-for-byte) ──────


def _build_dsse_pae(payload_type: str, body: bytes) -> bytes:
    """Pre-Authentication Encoding per DSSE v1 spec.

    Format: ``DSSEv1 SP <len(type)> SP <type> SP <len(body)> SP <body>`` where
    SP is ASCII space (0x20).
    """
    type_bytes = payload_type.encode("ascii")
    return (
        b"DSSEv1 "
        + str(len(type_bytes)).encode("ascii")
        + b" "
        + type_bytes
        + b" "
        + str(len(body)).encode("ascii")
        + b" "
        + body
    )


# ── Canonicalization (NFC then RFC 8785 — mirror server ADR-011 N1) ────────


def _nfc_normalize_strings(value: Any) -> Any:
    """Recursively NFC-normalize all strings in a JSON-able structure.

    Mirrors the server's Pydantic-validator behavior where ``@field_validator(mode="before")``
    applies ``unicodedata.normalize("NFC", ...)`` to every string. SDK uses frozen
    dataclasses (no validators), so we apply NFC manually before canonicalization.
    """
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {_nfc_normalize_strings(k): _nfc_normalize_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_nfc_normalize_strings(v) for v in value]
    return value


def _canonical_statement_bytes(statement_dict: dict[str, Any]) -> bytes:
    """Produce RFC 8785 canonical bytes after NFC normalization.

    Mirrors server-side ``rfc8785.dumps()`` pipeline. The ``rfc8785`` PyPI library
    (Trail of Bits) is the audited, no-deps reference implementation.
    """
    normalized = _nfc_normalize_strings(statement_dict)
    return rfc8785.dumps(normalized)


# ── Ed25519 + ML-DSA-44 verify (must match server attestation_provider.py) ──


def _verify_ed25519_with_context(signature: bytes, pae: bytes, public_key_bytes: bytes) -> bool:
    """Hash-and-sign with context: ``H(CONTEXT_STRING || PAE)`` → Ed25519 verify.

    Ed25519 doesn't natively support context strings (unlike ML-DSA-44 per
    FIPS 204). Server-side ``attestation_provider.py:124,205-209`` uses
    ``hashlib.sha256(CONTEXT_STRING + pae).digest()`` as the message — SDK
    mirrors exactly. Returns False on any verification failure (caller handles
    error_class mapping).
    """
    msg = hashlib.sha256(CONTEXT_STRING + pae).digest()
    try:
        pub = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        pub.verify(signature, msg)
        return True
    except (InvalidSignature, ValueError):
        return False


def _verify_mldsa44_with_context(signature: bytes, pae: bytes, public_key_bytes: bytes) -> bool:
    """ML-DSA-44 verify with FIPS 204 final ctx-string API.

    Calls liboqs-python's ``Signature.verify_with_ctx_str(message, signature,
    context, public_key)`` — introduced in liboqs-python 0.12.0 per FIPS 204
    Algorithms 2 & 3. Returns False on any verification failure.
    """
    try:
        with oqs.Signature("ML-DSA-44") as sig:
            return bool(sig.verify_with_ctx_str(pae, signature, CONTEXT_STRING, public_key_bytes))
    except Exception:
        # liboqs may raise RuntimeError on internal errors (corrupt key, etc.);
        # treat all such failures as verification-failed for fail-closed semantics.
        return False


# ── Top-level verifier ─────────────────────────────────────────────────────


def verify_attestation_locally(
    *,
    envelope: DSSEEnvelope,
    expected_digest: str,
    expected_environment: str,
    keys: AttestationVerifyKey,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    """Offline AEGIS attestation verifier.

    Mirrors server-side ``AttestationProvider.verify()`` byte-for-byte. Performs
    in order: envelope shape check, payload base64 decode, RFC 8785 re-canonicalization
    (catches tampering), Ed25519 verify (AND-of-2 first half), ML-DSA-44 verify
    (AND-of-2 second half), subject digest check, environment check, expiry check.

    Returns ``(True, None)`` on success; ``(False, error_class)`` on any failure.
    Error classes match server-side strings exactly so consumer code is identical
    whether using HTTP verify (D1) or offline verify (D2).

    Args:
        envelope: The DSSE envelope to verify (typically obtained from
            ``client.attestations.attest(...).envelope`` or stored offline).
        expected_digest: 64-character lowercase hex sha256 of the artifact under
            attest. Compared against the envelope's ``subject[0].digest["sha256"]``.
        expected_environment: One of ``"production" | "staging" | "preview"``.
            Compared against the envelope's ``predicate.governance.environment``.
        keys: Pinned :class:`AttestationVerifyKey` providing the Ed25519 + ML-DSA-44
            public keys. Consumers obtain these out-of-band (Sprint 5/E2
            verifier-kit, or project KMS/config).
        now: Optional reference time for expiry comparison. Defaults to
            ``datetime.now(timezone.utc)``. Useful for testing replay scenarios.

    Returns:
        ``(valid, error_class)`` tuple. On success: ``(True, None)``. On failure:
        ``(False, "AttestationXxxMismatch")`` matching one of the server-side
        error_class strings.

    Notes:
        Envelope shape errors (wrong signature count, missing required keyid
        prefixes) return ``(False, "AttestationSignatureSetIncomplete")`` to
        mirror server-side error_class semantics — they do NOT raise. This
        ensures consumer code that switches on ``error_class`` behaves
        identically across HTTP-verify (D1) and offline-verify (D2).
    """
    # 1. Envelope shape pre-check (mirror server: return error_class, do not raise).
    # Server-side `AttestationProvider._decode_envelope` returns
    # ("AttestationSignatureSetIncomplete") on missing/wrong-count sigs; SDK
    # mirrors so consumer code branching on `error_class` works identically
    # whether HTTP-verify (D1) or offline-verify (D2).
    if envelope.payload_type != PAYLOAD_TYPE:
        return (False, "AttestationPayloadTypeMismatch")
    if len(envelope.signatures) != 2:
        return (False, "AttestationSignatureSetIncomplete")

    ed_sig_entry = next(
        (s for s in envelope.signatures if s.keyid.startswith(ED25519_KEYID_PREFIX)),
        None,
    )
    ml_sig_entry = next(
        (s for s in envelope.signatures if s.keyid.startswith(MLDSA_KEYID_PREFIX)),
        None,
    )
    if ed_sig_entry is None or ml_sig_entry is None:
        return (False, "AttestationSignatureSetIncomplete")

    # 2. Base64-decode payload
    try:
        payload_bytes = base64.b64decode(envelope.payload, validate=True)
    except Exception:
        return (False, "AttestationPayloadDecodeFailed")

    # 3. Parse payload as JSON
    try:
        statement_dict = json.loads(payload_bytes)
    except Exception:
        return (False, "AttestationPayloadJsonInvalid")

    # 4. Re-canonicalize via RFC 8785 + NFC and compare to original — catches tampering
    canonical = _canonical_statement_bytes(statement_dict)
    if canonical != payload_bytes:
        return (False, "AttestationCanonicalBytesMismatch")

    # 5. Parse via SDK dataclasses
    try:
        statement = InTotoStatement.from_response(statement_dict)
    except Exception:
        return (False, "AttestationStatementShapeInvalid")

    # 6. Build DSSE PAE — same bytes both signatures verify against
    pae = _build_dsse_pae(envelope.payload_type, canonical)

    # 7. Verify Ed25519 (first half of AND-of-2)
    try:
        ed_sig_bytes = base64.b64decode(ed_sig_entry.sig, validate=True)
    except Exception:
        return (False, "AttestationEd25519SigDecodeFailed")
    if not _verify_ed25519_with_context(ed_sig_bytes, pae, keys.ed25519_public):
        return (False, "AttestationEd25519VerifyFailed")

    # 8. Verify ML-DSA-44 (second half of AND-of-2)
    try:
        ml_sig_bytes = base64.b64decode(ml_sig_entry.sig, validate=True)
    except Exception:
        return (False, "AttestationMLDSASigDecodeFailed")
    if not _verify_mldsa44_with_context(ml_sig_bytes, pae, keys.mldsa44_public):
        return (False, "AttestationMLDSAVerifyFailed")

    # 9. Subject digest check (lowercase-normalized per RFC 4122 + ADR-011 N1)
    if not statement.subject:
        return (False, "AttestationSubjectMissing")
    normalized_expected_digest = expected_digest.strip().lower()
    digest_in_envelope = statement.subject[0].digest.get("sha256", "").lower()
    if digest_in_envelope != normalized_expected_digest:
        return (False, "AttestationDigestMismatch")

    # 10. Environment check (case-sensitive Literal match)
    normalized_expected_environment = expected_environment.strip()
    if statement.predicate.governance.environment != normalized_expected_environment:
        return (False, "AttestationEnvironmentMismatch")

    # 11. Expiry check (ISO 8601 tz-aware)
    expires_at_str = statement.predicate.governance.expires_at
    try:
        expires_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    except Exception:
        return (False, "AttestationExpiresAtMalformed")
    if expires_dt.tzinfo is None:
        return (False, "AttestationExpiresAtMalformed")
    now_dt = now if now is not None else datetime.now(timezone.utc)
    if expires_dt <= now_dt:
        return (False, "AttestationExpired")

    return (True, None)
