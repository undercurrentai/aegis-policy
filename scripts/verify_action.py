"""Python entry-point for actions/verify-aegis-attestation/action.yml.

Loaded by the composite action's "Run verify_action.py" step. Wraps
`aegis-sdk[verify].verify_attestation_locally()` with:

  1. Canonical key bytes pinned at `keys/{ed25519-public.pem, mldsa65-public.bin}`
  2. Canonical policy at `policy/verifier-policy-v1.yaml`
  3. Runtime fingerprint cross-check (DiD: catches key-vs-policy drift the
     parity gate might miss across runner-cached action checkouts)
  4. Envelope parsing (inline JSON or `@path`)
  5. SDK verifier call (hybrid Ed25519 + ML-DSA-65 AND-of-2)
  6. policy_version strict-equal check (per upstream ADR-011 N3)
  7. Optional consumer-owned replay-detection via append-only file
  8. Emission of 9 outputs to $GITHUB_OUTPUT

The action layer wraps the verifier layer with 4 additional error_classes:

  - AttestationEnvelopeShapeInvalid   (envelope JSON cannot be parsed)
  - AttestationKeyFingerprintMismatch (committed bytes ≠ policy fingerprint)
  - AttestationPolicyVersionMismatch  (envelope policy_version ≠ expected)
  - AttestationReplayDetected         (decision_id seen prior in consumer store)

The 15 verifier-layer error_classes flow through unchanged. See
actions/verify-aegis-attestation/README.md §Error classes for the full
taxonomy + cosmic-flute §34.14 D for why these 4 are INTENTIONALLY OMITTED
from policy/verifier-policy-v1.yaml fail_closed_on (preserves SDK ↔ policy
parity invariant 15 vs 15).

Environment variables (set by action.yml):
    AEGIS_ENVELOPE              — DSSE envelope JSON string OR `@path/to/file`
    AEGIS_EXPECTED_DIGEST       — SHA-256 hex (64 chars, lowercased here)
    AEGIS_EXPECTED_ENVIRONMENT  — production | staging | preview
    AEGIS_POLICY_VERSION_EXPECTED — optional; empty = read from policy file
    AEGIS_REPLAY_STORE_PATH     — optional workspace-relative path
    AEGIS_ACTION_PATH           — github.action_path (set by action.yml)
    GITHUB_OUTPUT               — automatic Actions context var
    GITHUB_WORKSPACE            — automatic Actions context var

Test-fixture overrides (per cosmic-flute §34.14 L):
    AEGIS_KEYS_DIR_OVERRIDE     — alternate keys/ dir for self-test fixtures
    AEGIS_POLICY_PATH_OVERRIDE  — alternate policy YAML path for self-test

Sprint 5/E2 Phase C per cosmic-flute §34.6. Closes task #28.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from cryptography.hazmat.primitives import serialization

from aegis import (
    AttestationVerifyKey,
    DSSEEnvelope,
    verify_attestation_locally,
)


# ─────────────────────────────────────────────────────────────────────────────
# Path resolution
# ─────────────────────────────────────────────────────────────────────────────
# When loaded by the composite action: AEGIS_ACTION_PATH points at
#   <runner_temp>/_actions/undercurrentai/aegis-policy/<ref>/actions/verify-aegis-attestation/
# repo root = <action_path>/../../
# When invoked locally (unit tests / smoke): falls back to script location's parent.

def _resolve_repo_root() -> Path:
    action_path = os.environ.get("AEGIS_ACTION_PATH", "").strip()
    if action_path:
        # action.yml is at <repo>/actions/verify-aegis-attestation/; go up 2 dirs
        return Path(action_path).resolve().parent.parent
    # Fallback: this script lives at <repo>/scripts/verify_action.py
    return Path(__file__).resolve().parent.parent


REPO_ROOT = _resolve_repo_root()


def _fixture_mode_enabled() -> bool:
    """Defense-in-depth gate on the override env vars below.

    AEGIS_KEYS_DIR_OVERRIDE + AEGIS_POLICY_PATH_OVERRIDE are TEST-ONLY hooks
    used by the self-test workflow + unit tests to point verify_action.py at
    ephemeral fixture keys/policy instead of the production trust roots
    committed under `keys/` + `policy/`. They are NOT advertised in
    action.yml inputs.

    THREAT MODEL, stated honestly (v1.4.1 audit correction): this sentinel
    stops ACCIDENTAL env leakage — a stale $GITHUB_ENV from an earlier
    fixture-mode step, or a consumer cargo-culting the override vars. It
    does NOT stop a deliberately compromised prior step: anything that can
        echo "AEGIS_KEYS_DIR_OVERRIDE=./malicious-keys" >> $GITHUB_ENV
    can append AEGIS_INTERNAL_FIXTURE_MODE=1 in the same breath (and a
    prior step in the same job owns the runner anyway). Without the gate,
    accidental leakage alone would load non-production keys + policy whose
    fingerprints match each other, pass the runtime cross-check, and verify
    non-production envelopes as valid — that is the class this closes.

    Production consumers MUST NEVER set AEGIS_INTERNAL_FIXTURE_MODE. The
    self-test workflow + unit test helpers set it explicitly. This sentinel
    is intentionally undocumented in action.yml inputs / README so it
    can't be advertised as a public override knob.

    /quality-gate Phase 3 ultrathink probe 4 remediation.
    """
    return os.environ.get("AEGIS_INTERNAL_FIXTURE_MODE", "").strip() == "1"


def _keys_dir() -> Path:
    override = os.environ.get("AEGIS_KEYS_DIR_OVERRIDE", "").strip()
    if override and _fixture_mode_enabled():
        path = Path(override)
        return path if path.is_absolute() else REPO_ROOT / path
    return REPO_ROOT / "keys"


def _policy_path() -> Path:
    override = os.environ.get("AEGIS_POLICY_PATH_OVERRIDE", "").strip()
    if override and _fixture_mode_enabled():
        path = Path(override)
        return path if path.is_absolute() else REPO_ROOT / path
    return REPO_ROOT / "policy" / "verifier-policy-v1.yaml"


# ─────────────────────────────────────────────────────────────────────────────
# Output emission
# ─────────────────────────────────────────────────────────────────────────────

def _emit_outputs(outputs: dict[str, str]) -> None:
    """Write KEY=VALUE lines to $GITHUB_OUTPUT (or stdout for local smoke).

    Per GitHub Actions docs, output values containing newlines or special
    chars need heredoc syntax. AEGIS outputs are all single-line scalars
    (UUIDs, hex strings, ISO 8601, base64), so simple KEY=VALUE suffices.
    Multiline content (envelope payload) is NEVER emitted as an output —
    consumers re-fetch from the original envelope if they need it.
    """
    github_output = os.environ.get("GITHUB_OUTPUT", "").strip()
    # ENFORCE the single-line invariant the docstring asserts: a validly
    # signed envelope with a newline inside a governance field (decision_id,
    # environment, policy_version, ...) could otherwise inject a second
    # KEY=VALUE line — and on the failure paths that echo envelope fields,
    # `valid=true` after `valid=false` wins (v1.4.1 audit, defense-in-depth;
    # requires AEGIS-signed content, so scrub rather than reject).
    lines = [
        f"{k}={str(v).replace(chr(10), ' ').replace(chr(13), ' ')}"
        for k, v in outputs.items()
    ]
    body = "\n".join(lines) + "\n"
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fp:
            fp.write(body)
    else:
        # Local smoke: write to stdout with a marker so tests can capture
        sys.stdout.write("::github-output::\n" + body)


def _emit_error(error_class: str, detail: str) -> None:
    """Emit an Actions ::error:: log line for visibility in the step summary."""
    sys.stderr.write(f"::error::AEGIS verify failed [{error_class}]: {detail}\n")


def _emit_warning(message: str) -> None:
    """Emit an Actions ::warning:: log line."""
    sys.stderr.write(f"::warning::{message}\n")


def _emit_failure_outputs(
    error_class: str,
    *,
    decision_id: str = "",
    artifact_digest: str = "",
    environment: str = "",
    policy_version: str = "",
    expires_at: str = "",
    nonce: str = "",
    replay_checked: str = "false",
) -> None:
    """Emit `valid=false` + the failure error_class + best-effort echo of
    fields the action was able to extract before failing.

    All fields default to empty; the action's README documents that on
    failure the only reliable outputs are `valid` + `error-class`. Other
    fields are echoed only when the failure occurred AFTER they were
    parseable (e.g., AttestationReplayDetected fires AFTER predicate parse,
    so decision_id is populated then).
    """
    _emit_outputs({
        "valid": "false",
        "error-class": error_class,
        "decision-id": decision_id,
        "artifact-digest": artifact_digest,
        "environment": environment,
        "policy-version": policy_version,
        "expires-at": expires_at,
        "nonce": nonce,
        "replay-checked": replay_checked,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Pinned-key loading + fingerprint cross-check
# ─────────────────────────────────────────────────────────────────────────────

def _load_pinned_keys() -> tuple[bytes, bytes, dict[str, Any]]:
    """Load Ed25519 + ML-DSA-65 public keys from `keys/` + parse policy.

    Returns: (ed25519_raw, mldsa65_raw, policy_dict).
    Raises: FileNotFoundError / yaml.YAMLError / ValueError on malformed input.
    """
    keys_dir = _keys_dir()
    policy_path = _policy_path()

    ed25519_pem = (keys_dir / "ed25519-public.pem").read_bytes()
    ed25519_raw = serialization.load_pem_public_key(ed25519_pem).public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    mldsa65_raw = (keys_dir / "mldsa65-public.bin").read_bytes()

    with policy_path.open(encoding="utf-8") as fp:
        policy = yaml.safe_load(fp)

    return ed25519_raw, mldsa65_raw, policy


def _check_fingerprint_parity(
    ed25519_raw: bytes,
    mldsa65_raw: bytes,
    policy: dict[str, Any],
) -> str | None:
    """Return None on parity, or a detail string on mismatch.

    Mirrors scripts/check_fingerprints.py's gate logic but runs at action
    invocation time as a defense-in-depth check. The CI gate runs at PR-merge
    time; this runtime check catches the edge case where a runner cached an
    older action checkout that drifted from current main.
    """
    expected = policy.get("required_keyids", {})
    expected_ed = str(expected.get("ed25519", "")).strip().lower()
    expected_ml = str(expected.get("mldsa65", "")).strip().lower()

    actual_ed = hashlib.sha256(ed25519_raw).hexdigest()
    actual_ml = hashlib.sha256(mldsa65_raw).hexdigest()

    if actual_ed != expected_ed:
        return f"ed25519: bytes={actual_ed} policy={expected_ed}"
    if actual_ml != expected_ml:
        return f"mldsa65: bytes={actual_ml} policy={expected_ml}"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Envelope input parsing
# ─────────────────────────────────────────────────────────────────────────────

def _read_envelope_input(raw: str) -> dict[str, Any]:
    """Parse `AEGIS_ENVELOPE` input. Either inline JSON or `@path/to/file`.

    `@`-prefix triggers file read. Path is resolved relative to GITHUB_WORKSPACE
    when set (Actions runtime), or the current working directory otherwise.
    """
    raw = raw.strip()
    if raw.startswith("@"):
        rel = raw[1:]
        workspace = os.environ.get("GITHUB_WORKSPACE", "").strip()
        base = Path(workspace) if workspace else Path.cwd()
        path = Path(rel)
        full_path = path if path.is_absolute() else base / path
        return json.loads(full_path.read_text(encoding="utf-8"))
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Replay-detection (append-only file mechanism)
# ─────────────────────────────────────────────────────────────────────────────

def _check_and_append_replay_store(
    replay_store_rel: str,
    decision_id: str,
) -> tuple[bool, str | None]:
    """Check workspace-relative replay-store file for decision_id, append on miss.

    Returns: (already_seen, error_detail).
        already_seen=True  → decision_id was found in the store (replay attack)
        already_seen=False → decision_id appended; verification can proceed

    Per cosmic-flute §34.4 A.1: the store path is workspace-relative. Parent
    directories are auto-created. The file is touched if missing.
    """
    workspace = os.environ.get("GITHUB_WORKSPACE", "").strip()
    base = Path(workspace) if workspace else Path.cwd()
    rel_path = Path(replay_store_rel)
    store_file = rel_path if rel_path.is_absolute() else base / rel_path

    try:
        store_file.parent.mkdir(parents=True, exist_ok=True)
        store_file.touch(exist_ok=True)
        existing = {
            ln.strip()
            for ln in store_file.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        }
    except OSError as e:
        return False, f"replay store I/O error: {e}"

    if decision_id in existing:
        return True, None

    try:
        with store_file.open("a", encoding="utf-8") as fp:
            fp.write(f"{decision_id}\n")
    except OSError as e:
        # Failed to append; treat as a soft warning (cryptographic verify
        # already passed). Returning already_seen=False + a detail string
        # lets the caller decide whether to emit a warning or fail.
        return False, f"replay store append failed: {e}"

    return False, None


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    # ── Load pinned keys + policy ────────────────────────────────────────────
    try:
        ed25519_raw, mldsa65_raw, policy = _load_pinned_keys()
    except FileNotFoundError as e:
        _emit_error("AttestationKeyFingerprintMismatch", f"keys/policy file missing: {e}")
        _emit_failure_outputs("AttestationKeyFingerprintMismatch")
        return 1
    except (yaml.YAMLError, ValueError) as e:
        _emit_error("AttestationKeyFingerprintMismatch", f"policy YAML malformed: {e}")
        _emit_failure_outputs("AttestationKeyFingerprintMismatch")
        return 1

    # ── Fingerprint cross-check (DiD at runtime) ─────────────────────────────
    drift = _check_fingerprint_parity(ed25519_raw, mldsa65_raw, policy)
    if drift is not None:
        _emit_error("AttestationKeyFingerprintMismatch", drift)
        _emit_failure_outputs("AttestationKeyFingerprintMismatch")
        return 1

    keys = AttestationVerifyKey(
        ed25519_public=ed25519_raw,
        mldsa65_public=mldsa65_raw,
    )

    # ── Read action inputs from environment ──────────────────────────────────
    envelope_input = os.environ.get("AEGIS_ENVELOPE", "")
    expected_digest = os.environ.get("AEGIS_EXPECTED_DIGEST", "").strip().lower()
    expected_environment = os.environ.get("AEGIS_EXPECTED_ENVIRONMENT", "").strip()
    expected_policy_version = (
        os.environ.get("AEGIS_POLICY_VERSION_EXPECTED", "").strip()
        or str(policy.get("policy_version", "")).strip()
    )
    replay_store_path = os.environ.get("AEGIS_REPLAY_STORE_PATH", "").strip()

    # Defensive validation: AEGIS_EXPECTED_DIGEST format invariant. The SDK's
    # verify_attestation_locally will compare with the envelope's hex digest
    # and emit AttestationDigestMismatch on inequality — but a malformed input
    # (wrong length, non-hex chars) is a CONFIGURATION error, not a real
    # mismatch. Surface it with a distinct shape error so consumers can
    # differentiate. /quality-gate Phase 2 cycle 1 remediation of Lane B
    # Agent 1 F7.
    if expected_digest and (
        len(expected_digest) != 64
        or not all(c in "0123456789abcdef" for c in expected_digest)
    ):
        _emit_error(
            "AttestationEnvelopeShapeInvalid",
            f"AEGIS_EXPECTED_DIGEST malformed: must be 64 lowercase hex chars; "
            f"got len={len(expected_digest)}",
        )
        _emit_failure_outputs("AttestationEnvelopeShapeInvalid")
        return 1

    # ── Parse envelope ───────────────────────────────────────────────────────
    try:
        envelope_dict = _read_envelope_input(envelope_input)
    except (
        json.JSONDecodeError,
        FileNotFoundError,
        OSError,
        UnicodeDecodeError,
    ) as e:
        # OSError covers PermissionError + IsADirectoryError. UnicodeDecodeError
        # is NOT a subclass of OSError so listed explicitly. /quality-gate
        # Phase 2 cycle 1 remediation of Lane B Agent 1 F6.
        _emit_error("AttestationEnvelopeShapeInvalid", f"envelope input parse failed: {e}")
        _emit_failure_outputs("AttestationEnvelopeShapeInvalid")
        return 1

    try:
        envelope = DSSEEnvelope.from_response(envelope_dict)
    except Exception as e:
        # SDK's frozen-dataclass construction or its from_response factory
        # can raise on any structural problem (missing keys, wrong types,
        # etc.). All such failures collapse to a single composite-action-
        # layer error_class so consumers don't need to discriminate.
        _emit_error("AttestationEnvelopeShapeInvalid", f"DSSEEnvelope.from_response failed: {e}")
        _emit_failure_outputs("AttestationEnvelopeShapeInvalid")
        return 1

    # ── Verifier-layer crypto (SDK) ──────────────────────────────────────────
    valid, error_class = verify_attestation_locally(
        envelope=envelope,
        expected_digest=expected_digest,
        expected_environment=expected_environment,
        keys=keys,
    )
    if not valid:
        # SDK returns one of the 15 verifier-layer error_class strings.
        # Defense-in-depth: if SDK returned None unexpectedly, fall through
        # to a generic verifier-layer name (this should never fire on a
        # well-behaved SDK).
        ec = error_class or "AttestationStatementShapeInvalid"
        _emit_error(ec, "verifier-layer rejection (see SDK doc for cause)")
        _emit_failure_outputs(ec)
        return 1

    # ── Extract predicate for output + policy_version strict-equal ───────────
    # Past this point the envelope payload is canonical (verifier verified
    # H(canonical_bytes) → signature ↔ pinned key), so parsing the payload
    # again is safe and produces the same structure the verifier saw.
    try:
        payload_bytes = base64.b64decode(envelope.payload, validate=True)
        statement = json.loads(payload_bytes)
        governance = statement["predicate"]["governance"]
        decision_id = str(governance["decision_id"])
        artifact_digest = str(governance["artifact_digest"])
        environment = str(governance["environment"])
        policy_version = str(governance["policy_version"])
        expires_at = str(governance["expires_at"])
        nonce = str(governance.get("nonce", "") or "")
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        # Should be unreachable past a successful verifier-layer pass; this
        # branch is defense-in-depth for SDK contract drift.
        _emit_error("AttestationStatementShapeInvalid", f"predicate parse post-verify: {e}")
        _emit_failure_outputs("AttestationStatementShapeInvalid")
        return 1

    # Policy_version strict-equal (ADR-011 N3)
    if policy_version != expected_policy_version:
        detail = f"envelope={policy_version} expected={expected_policy_version}"
        _emit_error("AttestationPolicyVersionMismatch", detail)
        _emit_failure_outputs(
            "AttestationPolicyVersionMismatch",
            decision_id=decision_id,
            artifact_digest=artifact_digest,
            environment=environment,
            policy_version=policy_version,
            expires_at=expires_at,
            nonce=nonce,
        )
        return 1

    # ── Replay detection (consumer-owned; opt-in via input) ──────────────────
    replay_checked = "false"
    if replay_store_path:
        already_seen, detail = _check_and_append_replay_store(
            replay_store_path, decision_id
        )
        if already_seen:
            _emit_error(
                "AttestationReplayDetected",
                f"decision_id {decision_id} previously seen in {replay_store_path}",
            )
            _emit_failure_outputs(
                "AttestationReplayDetected",
                decision_id=decision_id,
                artifact_digest=artifact_digest,
                environment=environment,
                policy_version=policy_version,
                expires_at=expires_at,
                nonce=nonce,
                replay_checked="true",
            )
            return 1
        if detail is not None:
            # I/O issue reading or appending to the store; verify still
            # succeeds (cryptographic crypto passed + decision_id was not
            # previously observed by this run) but the audit trail is
            # incomplete — the store-write failed, so a subsequent run with
            # the SAME decision_id will not detect the replay. Surface
            # `replay-checked=false` so consumers gating on the audit-trail
            # invariant can fail-loud externally. /quality-gate Phase 2
            # cycle 1 remediation of Lane B Agent 1 F4.
            _emit_warning(f"replay-store-path I/O: {detail}")
            replay_checked = "false"
        else:
            replay_checked = "true"
    else:
        _emit_warning(
            "replay-store-path not set; consumer must implement replay "
            "detection externally (see policy/verifier-policy-v1.yaml "
            "replay_detection block + ADR-001 §Consumer-owned replay-detection "
            "responsibility)"
        )

    # ── Success ──────────────────────────────────────────────────────────────
    _emit_outputs({
        "valid": "true",
        "error-class": "",
        "decision-id": decision_id,
        "artifact-digest": artifact_digest,
        "environment": environment,
        "policy-version": policy_version,
        "expires-at": expires_at,
        "nonce": nonce,
        "replay-checked": replay_checked,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
