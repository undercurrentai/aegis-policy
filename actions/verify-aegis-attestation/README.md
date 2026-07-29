# `verify-aegis-attestation` — composite GitHub Action

Offline cryptographic verification of an AEGIS attestation envelope, using the
hybrid Ed25519 + ML-DSA-65 verifier from `aegis-sdk[verify]` against public
keys + verifier policy pinned in this repo (`undercurrentai/aegis-policy`).

Sprint 5/E2 — closes cosmic-flute §34 (tasks #28 + #119). See also:

- `policy/verifier-policy-v1.yaml` — canonical verifier policy artifact (v2.1.0+)
- `docs/architecture/adr/ADR-001-repo-trust-model.md` — trust model + consumer-owned replay-detection responsibility
- Upstream [ADR-011](https://github.com/undercurrentai/aegis-governance/blob/main/docs/architecture/adr/ADR-011-artifact-bound-aegis-attestations.md) — hybrid envelope spec + verifier-stateless trust model

---

## TL;DR

```yaml
- name: Verify AEGIS attestation
  uses: undercurrentai/aegis-policy/actions/verify-aegis-attestation@<sha>
  with:
    envelope: ${{ steps.fetch-attestation.outputs.envelope }}
    expected-digest: ${{ steps.build.outputs.artifact-sha256 }}
    expected-environment: production
```

**Pin by immutable commit SHA, never `@main` or `@v1.0.0`** — see ADR-001 §Decision for rationale.

---

## Reusable workflow alternative

For consumers who prefer job-level invocation over step-level (most new consumer repos), Sprint 5/E3 ships a companion reusable workflow:

```yaml
jobs:
  verify-attestation:
    uses: undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<sha>
    with:
      envelope: "@artifacts/envelope.json"
      expected-digest: ${{ needs.build.outputs.sha256 }}
      expected-environment: production
```

See [`REUSABLE-WORKFLOW.md`](REUSABLE-WORKFLOW.md) for full docs on the reusable workflow surface (when to use it vs. this composite Action, secrets propagation, permissions union, worked examples).

---

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `envelope` | YES | — | DSSE envelope JSON. Either inline JSON string OR `@path/to/file.json` (the `@` prefix triggers file read; path is workspace-relative). |
| `expected-digest` | YES | — | SHA-256 hex (64 lowercase chars) of the subject artifact. Compared byte-exactly against `envelope.predicate.subject[0].digest.sha256`. |
| `expected-environment` | YES | — | One of: `production` \| `staging` \| `preview`. Compared against `envelope.predicate.governance.environment`. |
| `policy-version-expected` | no | `""` | Strict-equal check against `envelope.predicate.governance.policy_version`. When empty, reads this repo's `policy/verifier-policy-v1.yaml policy_version` (currently `2.1.0`). |
| `replay-store-path` | no | `""` | Workspace-relative path to an append-only replay-detection file. Set to enable consumer-owned replay detection (see §Replay detection below). |
| `python-version` | no | `3.13` | Python version for `setup-python`. |
| `aegis-sdk-version` | no | `1.0.0` | PyPI version pin for `aegis-governance[verify]`. Used when `aegis-sdk-git-ref` is empty. |
| `aegis-sdk-git-ref` | no | `""` | Optional Git ref (commit SHA / tag / branch) to install `aegis-sdk` from. When set, overrides `aegis-sdk-version` (the PyPI default, which is the standard path — task #59 shipped 2026-05-15). See §Installation source below. |

---

## Outputs

| Output | Description |
|---|---|
| `valid` | `true` \| `false` — overall verification outcome. |
| `error-class` | Empty on success. On failure: an AEGIS-taxonomy error_class string (see §Error classes). |
| `decision-id` | `envelope.predicate.governance.decision_id` — UUID. |
| `artifact-digest` | `envelope.predicate.governance.artifact_digest` — echoed for downstream logging. |
| `environment` | `envelope.predicate.governance.environment` — echoed. |
| `policy-version` | `envelope.predicate.governance.policy_version` — echoed. |
| `expires-at` | `envelope.predicate.governance.expires_at` — ISO 8601 UTC. |
| `nonce` | `envelope.predicate.governance.nonce` — base64 (empty for `low`/`medium` risk_class). |
| `replay-checked` | `true` if `replay-store-path` was set and check ran; `false` otherwise. |

---

## Installation source

**Default (recommended): public PyPI.** `aegis-governance[verify]` has been published to PyPI since 2026-05-15 (task #59, AU-N-1) — the action's default `aegis-sdk-version: 1.0.0` installs it with no secret, no extra input:

```yaml
- uses: undercurrentai/aegis-policy/actions/verify-aegis-attestation@<sha>
  with:
    # no aegis-sdk-* inputs needed — installs aegis-governance[verify]==1.0.0 from PyPI
    # ...
```

**Override: commit-pinned Git install.** Set `aegis-sdk-git-ref` to install from a specific `undercurrentai/aegis-governance` ref instead. That repo is private, so the consumer workflow needs read access — see [GitHub docs on token authentication](https://docs.github.com/en/actions/security-guides/automatic-token-authentication). This was the only viable path before the PyPI publish; today it is for deliberately pinning an unreleased SDK commit.

(An earlier revision of this section said the PyPI path did not work yet; that stopped being true on 2026-05-15 and was corrected 2026-07-29.)

---

## Error classes

The action emits two layers of error_class strings on `valid: false`:

### Verifier-layer (15 strings, from `aegis-sdk[verify]`)

These correspond exactly to `policy/verifier-policy-v1.yaml fail_closed_on`. The SDK ↔ policy parity is enforced by `error-class-parity.yml` CI workflow on every PR to this repo.

| error_class | Cause |
|---|---|
| `AttestationPayloadTypeMismatch` | `envelope.payload_type` ≠ `application/vnd.in-toto+json` |
| `AttestationSignatureSetIncomplete` | Envelope shape: wrong sig count, or missing `ed25519:`/`ml-dsa-65:` keyid prefix |
| `AttestationPayloadDecodeFailed` | base64 decode of `envelope.payload` failed |
| `AttestationPayloadJsonInvalid` | Decoded payload is not valid JSON |
| `AttestationCanonicalBytesMismatch` | Re-canonicalized payload ≠ original (tampering) |
| `AttestationStatementShapeInvalid` | Statement fails Pydantic Literal/shape validation |
| `AttestationEd25519SigDecodeFailed` | base64 decode of Ed25519 signature failed |
| `AttestationEd25519VerifyFailed` | Ed25519 cryptographic verification failed |
| `AttestationMLDSASigDecodeFailed` | base64 decode of ML-DSA-65 signature failed |
| `AttestationMLDSAVerifyFailed` | ML-DSA-65 cryptographic verification failed |
| `AttestationSubjectMissing` | `statement.subject` array empty |
| `AttestationDigestMismatch` | `subject[0].digest.sha256` ≠ `expected-digest` input |
| `AttestationEnvironmentMismatch` | `predicate.governance.environment` ≠ `expected-environment` input |
| `AttestationExpiresAtMalformed` | `expires_at` not parseable as ISO 8601 UTC |
| `AttestationExpired` | `expires_at` ≤ now (TTL expired) |

### Composite-action-layer (4 strings, from this action)

These are enforced by `verify_action.py` BEFORE or AFTER the verifier-layer check. They are INTENTIONALLY OMITTED from `policy/verifier-policy-v1.yaml fail_closed_on` — preserves SDK ↔ policy parity invariant (15 vs 15) without forcing an SDK re-vendor. The action README is the canonical doc.

| error_class | Cause |
|---|---|
| `AttestationKeyFingerprintMismatch` | SHA-256 over `keys/*.{pem,bin}` ≠ `policy.required_keyids`. Runtime defense-in-depth on top of `fingerprint-parity.yml` CI gate. |
| `AttestationEnvelopeShapeInvalid` | Input `envelope` JSON cannot be parsed into `DSSEEnvelope` dataclass. |
| `AttestationPolicyVersionMismatch` | `envelope.predicate.governance.policy_version` ≠ expected (strict-equal per ADR-011 N3). |
| `AttestationReplayDetected` | `decision_id` found in the consumer-owned replay store at `replay-store-path`. |

---

## Replay detection

Per `policy/verifier-policy-v1.yaml replay_detection` + ADR-001 §"Consumer-owned replay-detection responsibility":

The AEGIS verifier (server-side `/attestations/verify` + SDK offline `verify_attestation_locally`) is **stateless by design**. The verifier does NOT track whether an envelope has been seen before. Replay detection is the **consumer's responsibility**.

This action provides an opt-in append-only-file mechanism via `replay-store-path`:

```yaml
- uses: undercurrentai/aegis-policy/actions/verify-aegis-attestation@<sha>
  with:
    envelope: ${{ steps.fetch.outputs.envelope }}
    expected-digest: ${{ steps.build.outputs.sha256 }}
    expected-environment: production
    replay-store-path: .github/.aegis-replay.log  # workspace-relative
```

Behavior:

- **`replay-store-path` set**: action checks the file for the current `decision_id`; if found → `valid: false` + `error-class: AttestationReplayDetected`. If not found → appends `decision_id` on success.
- **`replay-store-path` unset**: action emits `::warning::` in the step summary; verifies the envelope but does NOT gate on replay. The consumer's workflow must implement replay detection externally (DB unique constraint, Redis SETNX, etc.).

The append-only file is consumer-owned. The path may be workspace-relative (e.g., `.github/.aegis-replay.log`, resolved under `$GITHUB_WORKSPACE`) OR absolute (e.g., `/var/lib/aegis-replay/log` on a self-hosted runner with persistent FS); the action accepts both, consistent with the consumer-owned design intent. To persist across CI runs, the consumer commits the file (recommended workspace-relative path: `.github/.aegis-replay.log`) OR uses `actions/cache` keyed on a stable identifier OR uses absolute paths on persistent-FS self-hosted runners.

For `high`/`critical` risk_class, the predicate's `nonce` field provides a secondary uniqueness check on top of decision_id (per `policy/verifier-policy-v1.yaml replay_detection.mechanism_secondary`); consumers requiring nonce-aware behavior must hash `decision_id + nonce` into the store entry themselves — the action stores raw `decision_id` only.

**Concurrency caveat**: The append-only file mechanism is read-then-append WITHOUT filesystem-level locking. In CI matrix builds, `workflow_call:` fan-out, or self-hosted runners with shared persistent FS where two concurrent verifies of the SAME envelope race the read, both may see "not found" and both append — defeating replay detection within the race window. Consumers requiring strict concurrent replay detection MUST use a serialized store (DB unique constraint, Redis `SETNX`) — see `policy/verifier-policy-v1.yaml replay_detection.recommended_stores` for the canonical list.

**Retention**: The file grows unbounded. Recommended GC: prune entries with `expires_at < now()` periodically (the file is consumer-owned; cadence is the consumer's call). The action does NOT GC automatically.

**Store-write failure**: If the consumer-owned store is unreachable or appendable but write-fails post-read (e.g., disk full, EROFS), the action emits a `::warning::` and `replay-checked=false`. Cryptographic `valid=true` still holds (verifier-layer succeeded; the audit-trail-write failed). Consumers gating on the audit-trail invariant should also gate on `replay-checked == 'true'`, not just `valid == 'true'`.

---

## Example: minimal usage

```yaml
name: Deploy with AEGIS attestation gate
on:
  workflow_dispatch:
    inputs:
      envelope-path:
        description: "Path to DSSE envelope JSON"
        required: true
      artifact-digest:
        description: "SHA-256 hex of artifact"
        required: true

jobs:
  verify-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6

      - name: Verify AEGIS attestation
        id: verify
        uses: undercurrentai/aegis-policy/actions/verify-aegis-attestation@<sha>
        with:
          envelope: "@${{ inputs.envelope-path }}"
          expected-digest: ${{ inputs.artifact-digest }}
          expected-environment: production
          replay-store-path: .github/.aegis-replay.log
          # (default PyPI install; add aegis-sdk-git-ref only to pin an unreleased SDK commit)

      - name: Halt on verification failure
        if: steps.verify.outputs.valid != 'true'
        env:
          ERROR_CLASS: ${{ steps.verify.outputs.error-class }}
        run: |
          echo "::error::AEGIS verification failed: $ERROR_CLASS"
          exit 1

      - name: Deploy
        run: ./scripts/deploy.sh
        env:
          AEGIS_DECISION_ID: ${{ steps.verify.outputs.decision-id }}
```

---

## Example: gating on specific risk_class

The verifier itself does NOT check risk_class — it only validates the cryptographic envelope. Consumers gate on risk_class downstream. The snippet below uses the `env:` propagation pattern recommended by GitHub Security Lab to avoid script injection (https://securitylab.github.com/resources/github-actions-untrusted-input): `${{ ... }}` substitutions go into `env:` keys + are referenced as `$ENV_VAR` inside `run:`, NEVER substituted directly into shell.

```yaml
- name: Verify
  id: verify
  uses: undercurrentai/aegis-policy/actions/verify-aegis-attestation@<sha>
  with:
    envelope: ${{ steps.fetch.outputs.envelope }}
    expected-digest: ${{ steps.build.outputs.sha256 }}
    expected-environment: production

- name: Extract risk_class from envelope
  if: steps.verify.outputs.valid == 'true'
  id: risk
  env:
    # Pipe the same envelope JSON the action verified into env; we then
    # parse it via jq + base64 -d using ONLY shell variable expansion.
    # NEVER substitute ${{ ... }} directly into the `run:` block.
    ENVELOPE_JSON: ${{ steps.fetch.outputs.envelope }}
  run: |
    PAYLOAD_B64=$(jq -r '.payload' <<< "$ENVELOPE_JSON")
    RISK_CLASS=$(base64 -d <<< "$PAYLOAD_B64" | jq -r '.predicate.governance.risk_class')
    echo "risk_class=${RISK_CLASS}" >> "$GITHUB_OUTPUT"

- name: Halt on high/critical without manual review
  if: steps.risk.outputs.risk_class == 'high' || steps.risk.outputs.risk_class == 'critical'
  env:
    RISK_CLASS: ${{ steps.risk.outputs.risk_class }}
  run: |
    echo "::error::risk_class=$RISK_CLASS requires manual approval"
    exit 1
```

For consumers who prefer this gating logic packaged at the job level rather than as inline steps, see [`REUSABLE-WORKFLOW.md`](REUSABLE-WORKFLOW.md) §"Worked example: risk-class downstream gate" — Sprint 5/E3 ships this same pattern via `workflow_call:`.

---

## SHA-pinning expectations

Per ADR-001 §Decision and cosmic-flute §17 Critical 3:

- **Always pin by commit SHA**: `@<40-char-sha>`. Never `@main`, never `@v<tag>` (tags are mutable in some GitHub contexts).
- **Per-PR pin bumps**: consumer repos update their pinned SHA via reviewed PRs only.
- **Org-Ruleset enforcement** (Sprint 5/E1.5 Phase 7, live since 2026-05-12): `aegis-policy-critical-checks` requires `lint.yml` + `error-class-parity.yml` + `fingerprint-parity.yml` + CODEOWNERS approval before any merge to `main`. Bypass actors empty (admins included).
- **Transitive pins**: this composite action internally pins `actions/setup-python@a309ff8b...` (v6) at `action.yml`. Bumping the inner pin requires a PR to this repo; consumers transitively trust it via the outer `@<sha>` they pin.

---

## Versioning

This action's behavior is governed by:

1. **`policy/verifier-policy-v1.yaml policy_version`** — currently `2.1.0` (MINOR bump for `replay_detection:` block). Consumer pinning a SHA from before v2.1.0 (i.e., from before 2026-05-13) gets v2.0.0 behavior with NO action-level replay detection support.
2. **`aegis-sdk` version** — pinned via `aegis-sdk-version` input (default `1.0.0`) OR `aegis-sdk-git-ref`.
3. **`keys/*` fingerprints** — currently from Sprint 5/E1.5 ceremony 2026-05-10. Rotations follow `docs/key-rotation-runbook.md` + bump `policy_version` MAJOR.

---

## References

- Cosmic-flute §34 — Sprint 5/E2 execution plan
- ADR-001 §Decision — trust model + replay-detection responsibility
- ADR-002 — Sprint 5/E1.5 key ceremony 2026-05-10
- ADR-003 — ML-DSA-44 → ML-DSA-65 migration consequence
- Upstream ADR-011 — hybrid envelope spec
- Upstream ADR-012 — algorithm migration + uniform prefix-hash-and-sign
- `policy/verifier-policy-v1.yaml` — canonical verifier policy
- `scripts/verify_action.py` — Python entry-point loaded by this action
