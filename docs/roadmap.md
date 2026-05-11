# Roadmap

Sprint 5 / E1-E3 + Sprint 6 / F1-F2 + Sprint 7 / G1-G3 of the rigor-aegis-attestations protocol. See cosmic-flute §22.11 / §23.14 / §24.12 / §25.11 OOS tables for canonical scope splits.

| Phase | Status | Description | Tracking |
|---|---|---|---|
| **Sprint 5 / E1** | ✅ shipped 2026-05-09 (commit `9c25b38`) | Repo bootstrap + governance scaffolding + contract vendoring + canonical verifier-policy `v1.0.0` (placeholder keys) | PR #1 (squash-merged via admin) |
| **Sprint 5 / E1.5** | 🟢 in-progress 2026-05-10 (Phases 1-5 shipped; Phases 6-8 pending) | Real Ed25519 + ML-DSA-65 keypair via GCP Cloud KMS (`aegis-attestation-ed25519`, `aegis-attestation-mldsa65`; SOFTWARE protection — HSM unavailable for both algorithms per cosmic-flute §28.17) + server-side `KMSAttestationSigner` rewire + commit `keys/ed25519-public.pem` + `keys/mldsa65-public.bin` + fill in `policy/verifier-policy-v1.yaml required_keyids` + `policy_version` v1.0.0 → v2.0.0 (BREAKING algorithm migration ML-DSA-44 → ML-DSA-65 per upstream ADR-012). **AEGIS-self-tune-class gate cleared 2026-05-10 (decision_id `9eae3455…`).** Org-level GitHub Ruleset configuration deferred to Phase 7 (admin-level, out-of-repo). | Phase 4: aegis-governance PR #169 + audit #171 (squash `7e422b2`). Phase 5: this PR (merge SHA captured at squash-merge time). Phases 6 (prod deploy) + 7 (org-Ruleset) + 8 (live re-verify) downstream. |
| **Sprint 5 / E2** | ☐ planned | Composite GitHub Action `verify-aegis-attestation` (`actions/verify-aegis-attestation/action.yml`). Wraps `aegis-sdk[verify]` + key-fingerprint pinning + cosign-signed kit container release `ghcr.io/undercurrentai/aegis-policy`. | Separate plan + PR |
| **Sprint 5 / E3** | ☐ planned | Reusable workflow `.github/workflows/aegis-verify-attestation.yml` (`workflow_call` trigger). Job-level orchestration consumed by the 19 non-`aegis-policy` portfolio repos (this repo itself is the 20th in the portfolio + the kit's source — it does not consume its own kit). Resolves the `verifier_policy_artifact` reference at `schema/attestation_predicate_v1.yaml:128`. | Separate plan + PR |
| **Sprint 6 / F1** | ☐ planned | `aegis-governance/.github/workflows/aegis-deploy.yml` integration (dogfood). aegis-governance becomes its own first verifier-kit consumer. CLAUDE.md §8 Ask-First gate. | Separate plan + PR (on `aegis-governance`) |
| **Sprint 6 / F2** | ☐ planned | `openclaw-operator-os/scripts/blue-green-deploy.sh` integration (dogfood across 3 substrates per cosmic-flute §11.7). | Separate plan + PR (on `openclaw-operator-os`) |
| **Sprint 7 / G1** | ☐ planned | Org-level GitHub Ruleset for required `aegis-attestation-verified` status check across all 19 (now 20) portfolio repos. Admin-level operation. | Org settings change, not a code PR |
| **Sprint 7 / G2** | ☐ planned | `aegis-gtm` pilot rollout — first non-aegis-governance consumer. Validates verifier-kit ergonomics for the typical Vercel-deployed website. | Separate plan + PR (on `aegis-gtm`) |
| **Sprint 7 / G3** | ☐ planned | Roll out to remaining 18 production-bound repos. Tracked via Linear when Step 2 of the operator-OS plan wires Linear webhook. | Linear epic per repo |

## Phase 2 (post-Sprint 7) — ecosystem-compat

Out of the rigor-aegis-attestations protocol scope; planned for the cosmos-mixing-snuggly successor protocol:
- Cosign sidecar (single-sig DSSE+ECDSA-P256 alternative envelope path) for ecosystem interop
- TUF-based key distribution (replacing current Git-versioned PEM model if external integrators require it)
- JWKS endpoint on `aegis-governance` API server (`/.well-known/aegis-keys.json`) for dynamic key discovery — contradicts ADR-011 N5 if runtime-fetched, so design carefully
- Bundle-format support (`application/vnd.in-toto.bundle`, `.intoto.jsonl`) for attestation streams

## Cumulative dependency graph

```
        Sprint 1 (ADR + schema)
        ✅ aegis-governance@a5c0bfd
                │
                ▼
        Sprint 2 (Pydantic + provider + DB)
        ✅ aegis-governance@84aa73c
                │
                ▼
        Sprint 3 (HTTP API)
        ✅ aegis-governance@7e45115b + hotfix a6fdaae
                │
                ▼
        Sprint 4/D1 (SDK HTTP client)
        ✅ aegis-governance@af560cb + audit 1637468
                │
                ▼
        Sprint 4/D2 (SDK offline verifier)
        ✅ aegis-governance@fb2dec3 + audit 37f8608
                │
                ▼
        ┌───────────────────────────┐
        │ Sprint 5/E1 (THIS REPO)   │
        │ ✅ aegis-policy@9c25b38    │
        └───────────────┬───────────┘
                        │
                        ▼
        Sprint 5/E1.5 Phase 4 (server uniform-KMS + ML-DSA-65 + ADR-012)
        ✅ aegis-governance@7e422b2 (PR #169 + audit #171)
                        │
                        ▼
        Sprint 5/E1.5 Phase 5 (THIS PR — real keys + policy v2.0.0)
        🟡 aegis-policy@<merge-sha-captured-post-squash>
                        │
                        ├──► Sprint 5/E1.5 Phase 6 (prod redeploy)
                        ├──► Sprint 5/E1.5 Phase 7 (org-Ruleset)
                        ├──► Sprint 5/E1.5 Phase 8 (live re-verify)
                        │
                        ├──► Sprint 5/E2 (composite Action)
                        │
                        ├──► Sprint 5/E3 (reusable workflow)
                        │           │
                        │           ▼
                        │   Sprint 6/F1 (aegis-deploy.yml dogfood)
                        │   Sprint 6/F2 (openclaw blue-green dogfood)
                        │           │
                        │           ▼
                        └─► Sprint 7/G1+G2+G3 (org Ruleset + 20-repo rollout)
```
