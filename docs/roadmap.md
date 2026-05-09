# Roadmap

Sprint 5 / E1-E3 + Sprint 6 / F1-F2 + Sprint 7 / G1-G3 of the rigor-aegis-attestations protocol. See cosmic-flute §22.11 / §23.14 / §24.12 / §25.11 OOS tables for canonical scope splits.

| Phase | Status | Description | Tracking |
|---|---|---|---|
| **Sprint 5 / E1** | ✅ shipped 2026-05-09 | Repo bootstrap + governance scaffolding + contract vendoring + canonical verifier-policy `v1.0.0` (placeholder keys) | This commit / PR |
| **Sprint 5 / E1.5** | ☐ planned | Real Ed25519 + ML-DSA-44 keypair generation ceremony + GCP KMS aliases (`aegis-attestation-ed25519`, `aegis-attestation-mldsa44`) + server-side `attestation_keys.py:155 NotImplementedError` removal + commit `keys/ed25519-public.pem` + `keys/mldsa44-public.bin` + fill in `policy/verifier-policy-v1.yaml required_keyids` + bump `policy_version`. **Requires Josh-explicit-✅ AEGIS-self-tune-class gate per cosmic-flute §5.** Org-level GitHub Ruleset configuration (admin-level, out-of-repo). | Separate plan + PR (AEGIS-self-tune class) |
| **Sprint 5 / E2** | ☐ planned | Composite GitHub Action `verify-aegis-attestation` (`actions/verify-aegis-attestation/action.yml`). Wraps `aegis-sdk[verify]` + key-fingerprint pinning + cosign-signed kit container release `ghcr.io/undercurrentai/aegis-policy`. | Separate plan + PR |
| **Sprint 5 / E3** | ☐ planned | Reusable workflow `.github/workflows/aegis-verify-attestation.yml` (`workflow_call` trigger). Job-level orchestration consumed by all 19 portfolio consumer repos. Resolves the `verifier_policy_artifact` reference at `schema/attestation_predicate_v1.yaml:128`. | Separate plan + PR |
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
        │ Sprint 5/E1 (THIS REPO!)  │
        │ ✅ aegis-policy@<tbd>      │
        └───────────────┬───────────┘
                        │
                        ├──► Sprint 5/E1.5 (real keys + KMS)
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
