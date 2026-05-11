# Key Rotation Runbook

Procedure for rotating the canonical Ed25519 + ML-DSA-65 attestation keys. Keys are KMS-resident (GCP Cloud KMS at SOFTWARE protection level — HSM unavailable for both `EC_SIGN_ED25519` and `PQ_SIGN_ML_DSA_65` per [ADR-002](architecture/adr/ADR-002-key-ceremony-2026-05-10.md) §"Hardware + software"). Private bytes never leave KMS; rotation produces NEW public bytes that get committed to this repo.

## When to rotate

- **Suspected compromise** of the KMS keyring or service account → emergency rotation (see §"Suspected compromise" below)
- **Scheduled audit cadence** — every 24 months minimum, sooner if external review recommends
- **NIST guidance update** — if FIPS 204 successor algorithm lands in GCP KMS and supplants ML-DSA-65
- **Service-account compromise** at `aegis-attestation-signer@undercurrent-production.iam.gserviceaccount.com` (rotate the SA AND the keys — the SA is the only principal with `roles/cloudkms.signerVerifier` on the `aegis-attestation` keyring)

## Steady-state rotation procedure (KMS-only)

### Step 1: Provision new key version in GCP KMS

```bash
PROJECT=undercurrent-production
LOCATION=us-central1
KEYRING=aegis-attestation

# Rotate Ed25519 (new version on existing key resource)
gcloud kms keys versions create \
  --key=aegis-attestation-ed25519 --keyring=$KEYRING \
  --location=$LOCATION --project=$PROJECT

# Rotate ML-DSA-65 (new version on existing key resource)
gcloud kms keys versions create \
  --key=aegis-attestation-mldsa65 --keyring=$KEYRING \
  --location=$LOCATION --project=$PROJECT
```

KMS auto-assigns the next version number (`2`, `3`, etc.). Old versions remain queryable for verifying historical attestations until explicitly destroyed.

### Step 2: Extract new public-key bytes

```bash
# Ed25519: PEM-wrapped 32B raw (standard format; cryptography library handles it)
gcloud kms keys versions get-public-key <new-version> \
  --key=aegis-attestation-ed25519 --keyring=$KEYRING \
  --location=$LOCATION --project=$PROJECT \
  --output-file=/tmp/ed25519-public-new.pem

# ML-DSA-65: X.509 SubjectPublicKeyInfo PEM (2,726B); needs manual ASN.1 DER scan
# because cryptography (≤44.x) doesn't yet recognize OID 2.16.840.1.101.3.4.3.18
gcloud kms keys versions get-public-key <new-version> \
  --key=aegis-attestation-mldsa65 --keyring=$KEYRING \
  --location=$LOCATION --project=$PROJECT \
  --output-file=/tmp/mldsa65-public-new.pem

# Extract raw 1952B from the PEM via the in-repo helper script
python3 scripts/extract_mldsa65_raw.py /tmp/mldsa65-public-new.pem /tmp/mldsa65-public-new.bin
```

### Step 3: Compute new fingerprints

```bash
# Ed25519: SHA-256 over the RAW 32 bytes (PEM-unwrapped via cryptography library)
python3 -c "
from cryptography.hazmat.primitives.serialization import load_pem_public_key, Encoding, PublicFormat
import hashlib
raw = load_pem_public_key(open('/tmp/ed25519-public-new.pem','rb').read()).public_bytes(Encoding.Raw, PublicFormat.Raw)
print('ed25519:', hashlib.sha256(raw).hexdigest())
"

# ML-DSA-65: SHA-256 over the raw 1952B
shasum -a 256 /tmp/mldsa65-public-new.bin
```

### Step 4: Configure dual-key signing for rollover window

> ⚠️ **DEFERRED INFRASTRUCTURE — not implemented in `aegis-governance@7e422b2`**
>
> As of Sprint 5/E1.5 Phase 4 (aegis-governance@`7e422b2`), `AttestationProvider.issue()` signs with a SINGLE key version. The dual-sign window described below is **target-state architecture** for routine rotations once dual-version signing lands (separate sprint — likely post Sprint 5/E2). For ANY rotation performed today (E1.5-era), use the **single-cutover variant** below instead of Step 4 as written.
>
> **Single-cutover variant (E1.5-era; pre-dual-sign)**:
>
> 1. Provision new KMS key version (Step 1). Old version stays ENABLED.
> 2. Extract public bytes + compute fingerprints (Steps 2-3).
> 3. Switch Cloud Run env var to point at new version: `--update-env-vars=AEGIS_ATTESTATION_KMS_VERSION=2` (atomic flip; new envelopes sign under v2 immediately).
> 4. Commit new public keys + bump policy/required_keyids in this repo (Step 5).
> 5. Old-version-pinned consumers will fail-closed on the next attestation they try to verify (per `fail_closed_on: signature_verify_failed`). They must bump their pinned aegis-policy SHA within their attestation TTL window (default 24h for low/medium risk_class; 1h for high/critical). Any in-flight envelopes signed under v1 remain verifiable by any consumer still on the old pin until their TTL expires.
>
> Acceptance criterion for single-cutover: ALL consumer repos must bump their pinned SHA within the attestation TTL window of the cutover. This is feasible at the Sprint-5/E1.5 scale (no production consumers yet — Sprint 6 dogfood is the first); it does NOT scale to Sprint 7's 19-repo rollout, which is why dual-sign infrastructure is on the roadmap.

The **future-state dual-sign procedure** (target architecture once `AttestationProvider.issue()` supports multi-version signing):

Server-side (`aegis-governance`) would be configured to sign under BOTH the old (`v1`) AND the new key version for the rollover window via env-var bump on the Cloud Run service:

```bash
gcloud run services update aegis-api \
  --region=us-central1 --project=$PROJECT \
  --update-env-vars=AEGIS_ATTESTATION_KMS_VERSION_OLD=1,AEGIS_ATTESTATION_KMS_VERSION_NEW=2,AEGIS_ATTESTATION_DUAL_SIGN_UNTIL=2026-XX-XXT00:00:00Z
```

A future `AttestationProvider.issue()` would read `DUAL_SIGN_UNTIL`; if the current time is before that deadline, it would produce a DSSE envelope with **4 signatures** (old-Ed25519, old-ML-DSA-65, new-Ed25519, new-ML-DSA-65). Consumers verify with AND-of-2 by selecting the (Ed25519, ML-DSA-65) pair whose `keyid` prefixes match their pinned `required_keyids`. After the deadline, only the new version signs (back to 2 signatures per envelope).

**Rollover window (future)**: 24 hours by default (matches `policy/verifier-policy-v1.yaml ttl_per_risk_class.low|medium`). Can be shortened to 1h for high-severity incident rotation.

### Step 5: Commit new public keys + bump fingerprints

In this repo, open a new branch:

```bash
git checkout -b feat/key-rotation-YYYY-MM-DD

# Replace public-key files with new bytes
mv /tmp/ed25519-public-new.pem keys/ed25519-public.pem
mv /tmp/mldsa65-public-new.bin keys/mldsa65-public.bin

# Update policy/verifier-policy-v1.yaml required_keyids with new fingerprints
# (manual edit — replace the hex values from Step 3)

# Run the fingerprint-parity gate locally to confirm match
python3 scripts/check_fingerprints.py
# Expect: ✓ FINGERPRINT PARITY HOLDS 2-vs-2

# Bump policy_version MAJOR (required_keyids changed → contract tightening)
# In policy/verifier-policy-v1.yaml: policy_version "2.0.0" → "3.0.0" (or current+1 MAJOR)
# Add entry to policy/CHANGELOG.md describing the rotation
```

### Step 6: Open PR for review

```bash
git push origin feat/key-rotation-YYYY-MM-DD
gh pr create --title "feat(keys): rotate canonical Ed25519 + ML-DSA-65 keys (YYYY-MM-DD)" \
  --body "$(cat <<'EOF'
## Summary

Routine key rotation per `docs/key-rotation-runbook.md`. New KMS key versions (Ed25519 v<N>, ML-DSA-65 v<N>); old versions retained for verification of historical attestations until destroyed.

## Verification

- [x] `scripts/check_fingerprints.py` PASS (2-vs-2)
- [x] `scripts/check_error_class_parity.py` PASS (15-vs-15; unchanged)
- [x] Server-side dual-sign window configured: `AEGIS_ATTESTATION_DUAL_SIGN_UNTIL=...`
- [x] AEGIS Stage-2 self-eval submitted: decision_id `<UUID>`

## Test plan

- Cloud Run `/ready` returns 200 with `attestations.ok: true` post-deploy
- §27 Tier 4 end-to-end probes (issue + retrieve + verify) PASS against post-rotation production
- Consumer-repo SHA pin updates land within 24h rollover window (track via Linear epic)
EOF
)"
```

### Step 7: CODEOWNERS approval + merge

`@ThermoclineLeviathan` reviews. AEGIS Stage-2 self-eval submitted (governance-mutating + AEGIS-self-tune class → expect Josh-explicit-✅ override per cosmic-flute §5 — rotation IS a self-tune-class action).

### Step 8: Consumer-repo SHA pin synchronization

After merge, all 20 portfolio repos pinning aegis-policy by SHA need to bump their pin to the new merge SHA within the dual-sign window (default 24h). Coordinate via the Linear epic that tracks the rotation.

For repos that lag the bump: their old pin keeps working as long as the old KMS key version still exists (signatures verify against old public keys). Risk increases the longer they lag; close all pin-bump PRs before destroying the old KMS key version.

### Step 9: Destroy old KMS key version (eventually)

After all consumers have bumped + 30-day safety window has elapsed:

```bash
gcloud kms keys versions destroy 1 \
  --key=aegis-attestation-ed25519 --keyring=$KEYRING \
  --location=$LOCATION --project=$PROJECT
  # GCP applies the key resource's configured destroy_scheduled_duration
  # (default 30 days; range 24h to 30d). To override at create-time:
  #   gcloud kms keys create ... --destroy-scheduled-duration=24h
```

GCP enforces a configurable grace period (default **30 days**; range 24h to 30d, set via `--destroy-scheduled-duration` at key-creation time per [GCP KMS docs](https://cloud.google.com/kms/docs/destroy-restore)) during which `versions restore` can resurrect. The Sprint 5/E1.5 ceremony's `-sw` experimental probe (per [ADR-002](architecture/adr/ADR-002-key-ceremony-2026-05-10.md) §"Cleanup state at ceremony close") used the default 30d, hard-destroying 2026-06-09. After the grace period elapses, hard-destruction is irreversible.

## Emergency rotation (suspected compromise)

If a private KMS key version OR the service account `aegis-attestation-signer` is suspected compromised:

1. **Immediately**: email `security@undercurrentholdings.com` + open a private GitHub vulnerability report. **Do NOT open a public issue or PR mentioning the compromise.**
2. **Within 30 min**: disable the compromised KMS key version:

   ```bash
   gcloud kms keys versions disable <compromised-version> \
     --key=aegis-attestation-ed25519 --keyring=$KEYRING \
     --location=$LOCATION --project=$PROJECT
   ```

   Disabling makes the version unusable for signing; existing-signature verification depends on `policy_version_compatibility` (strict-equal blocks them; semver-major-equal grants grace).
3. **Within 2h**: provision new KMS key versions (Step 1 above), extract bytes (Step 2), compute fingerprints (Step 3), configure compressed dual-sign window (Step 4 with `DUAL_SIGN_UNTIL` = NOW + 4 hours instead of 24h).
4. **Within 4h**: open the rotation PR (Steps 5-6), expedited CODEOWNERS review.
5. **Within 12h**: all consumer-repo pin bumps + destroy compromised KMS version.
6. **Post-incident**: ADR documenting the compromise + lessons learned + any architectural changes (consider rotating the service account, tightening IAM, enabling Cloud KMS HSM if it becomes available).

## Multi-keyholder growth path

The procedures above assume sole-keyholder per [ADR-001](architecture/adr/ADR-001-repo-trust-model.md). When the team grows beyond one engineer, update CODEOWNERS to require 2-of-N approvals on `keys/` + `schema/` + `policy/` paths (per ADR-001 §"When the team grows"); rotation procedures otherwise unchanged.

## References

- [ADR-001](architecture/adr/ADR-001-repo-trust-model.md) — Repo trust model
- [ADR-002](architecture/adr/ADR-002-key-ceremony-2026-05-10.md) — Initial key ceremony (Sprint 5/E1.5)
- [ADR-003](architecture/adr/ADR-003-ml-dsa-44-to-65-migration.md) — ML-DSA-44 → ML-DSA-65 algorithm migration
- Upstream **ADR-011** (artifact-bound AEGIS attestations + N4 distinct-keys invariant) at `aegis-governance@7e422b2`
- Upstream **ADR-012** (uniform prefix-hash-and-sign under KMS) at `aegis-governance@7e422b2`
- Cosmic-flute §5 — AEGIS thresholds (key rotation = AEGIS-self-tune class)
- Cosmic-flute §17 Critical 3 — Policy-bootstrap protection
- Cosmic-flute §28.17 — Phase 1 captured ceremony state (canonical fingerprints + KMS resource provenance)
