# Verifier Policy Changelog

Tracks `policy/verifier-policy-v1.yaml policy_version` bumps independently of the repo-level `CHANGELOG.md`. This separation lets consumers pin a specific `policy_version` without coupling to repo-level bookkeeping.

Format: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html) — MAJOR for field removal / contract tightening, MINOR for backward-compatible additions, PATCH for documentation-only fixes within an entry.

---

## [1.0.0] — 2026-05-09

Initial canonical verifier policy artifact. Sprint 5/E1 ship.

### Defined

- **Crypto contract**: Ed25519 + ML-DSA-44 hybrid AND-of-2 per ADR-011; CONTEXT_STRING `aegis-attestation-v1`; payload_type `application/vnd.in-toto+json`; key sizes (Ed25519 32B, ML-DSA-44 1312B).
- **Required keyids**: PLACEHOLDER fingerprints — real values land in Sprint 5/E1.5 ceremony. Until E1.5, this policy artifact is **not consumable for verification** by E2/E3 (they will fail with placeholder check).
- **Required context bindings** (6): repository, workflow_ref, run_id, run_attempt, environment, subject_digest.
- **Required predicate fields** (8): decision_id, artifact_digest, environment, risk_class, policy_version, issued_at, expires_at, gate_pass_states.
- **TTL per risk_class**: low/medium 24h, high/critical 1h. Quarterly-review cadence; next review 2026-08-09.
- **Nonce policy**: required for `high` and `critical` risk_class; 32-byte (256-bit).
- **Fail-closed conditions** (15): full SDK error_class taxonomy mirror, parity-enforced by `error-class-parity.yml` CI workflow.
- **Policy_version_compatibility**: `strict-equal` (consumers pinning v1.0.0 must verify only against v1.0.0 attestations).

### Notes

- The 15-entry `fail_closed_on` list mirrors the post-Sprint-4/D2-audit SDK on `aegis-governance` main `37f8608`. Cosmic-flute §26.18 documents one judgment-call deviation from the Ultraplan refinement: Ultraplan recommended a 14-entry list dropping `signature_set_incomplete` on the assumption that envelope shape errors raise `ValueError`. Post-audit (commit `7700ce0` inside PR #168) the SDK returns `(False, "AttestationSignatureSetIncomplete")`. SDK source is the source-of-truth; 15 entries is correct.

### Upstream

- Cosmic-flute plan §26: `~/.claude/plans/let-s-plan-this-cosmic-flute.md`
- ADR-011: `https://github.com/undercurrentai/aegis-governance/blob/main/docs/architecture/adr/ADR-011-artifact-bound-aegis-attestations.md`
- SDK source-of-truth: `aegis-sdk@v0.6.1` (`aegis-governance` main `37f8608`)
