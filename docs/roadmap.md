# Roadmap

Sprint 5 / E1-E3 + Sprint 6 / F1-F2 + Sprint 7 / G1-G3 of the rigor-aegis-attestations protocol. See cosmic-flute §22.11 / §23.14 / §24.12 / §25.11 OOS tables for canonical scope splits.

| Phase | Status | Description | Tracking |
|---|---|---|---|
| **Sprint 5 / E1** | ✅ shipped 2026-05-09 (commit `9c25b38`) | Repo bootstrap + governance scaffolding + contract vendoring + canonical verifier-policy `v1.0.0` (placeholder keys) | PR #1 (squash-merged via admin) |
| **Sprint 5 / E1.5** | ✅ shipped 2026-05-12 | Real Ed25519 + ML-DSA-65 keypair via GCP Cloud KMS (`aegis-attestation-ed25519`, `aegis-attestation-mldsa65`; SOFTWARE protection — HSM unavailable for both algorithms per cosmic-flute §28.17) + server-side `KMSAttestationSigner` rewire + commit `keys/ed25519-public.pem` + `keys/mldsa65-public.bin` + fill in `policy/verifier-policy-v1.yaml required_keyids` + `policy_version` v1.0.0 → v2.0.0 (BREAKING algorithm migration ML-DSA-44 → ML-DSA-65 per upstream ADR-012). **AEGIS-self-tune-class gate cleared 2026-05-10 (decision_id `9eae3455…`).** All 8 phases shipped (incl. org-level GitHub Ruleset Phase 7 + Tier 4e live re-verify Phase 8). | aegis-governance v1.2.0 → v1.2.4 chain (Phases 6-8 + B1+B2+B3 hotfixes); aegis-policy `5223f58` (Phase 5); cosmic-flute §32 ship capture |
| **Sprint 5 / E2** | ✅ shipped 2026-05-13 (commit `19a751e`) | Composite GitHub Action `verify-aegis-attestation` (`actions/verify-aegis-attestation/action.yml`). Wraps `aegis-sdk[verify]` + key-fingerprint pinning + consumer-owned replay-detection (per `policy/verifier-policy-v1.yaml replay_detection:` block + ADR-001 §"Consumer-owned replay-detection responsibility"). Bundled: action.yml + README.md + `scripts/verify_action.py` entry-point + `tests/test_verify_action.py` (12 unit tests) + `tests/fixtures/` (ephemeral keypair + 3 envelopes + test policy) + `.github/workflows/e2-action-selftest.yml` (5-job self-test, `workflow_dispatch:`-only until task #59 PyPI publish). Closes cosmic-flute tasks #119 + #28. (Cosign-signed kit container release `ghcr.io/undercurrentai/aegis-policy` deferred to Phase 2 ecosystem-compat per cosmic-flute §34.13 OOS.) | PR #5 (squash-merged via admin per cosmic-flute §34.17 sole-keyholder pattern; in-flight CI job-name remediation `ff0ec71`) |
| **Sprint 5 / E3** | ✅ shipped 2026-05-14 (commit `c34c783`) | Reusable workflow `.github/workflows/aegis-verify-attestation.yml` (`workflow_call` trigger). Job-level orchestration consumed by the 19 non-`aegis-policy` portfolio repos (this repo itself is the 20th in the portfolio + the kit's source — it does not consume its own kit). Resolves the `verifier_policy_artifact` reference at `schema/attestation_predicate_v1.yaml:128`. Bundles task #129 deferred E2 doc-flips per cosmic-flute §34.17.3 + §35. | PR #6 (squash-merged via admin per cosmic-flute §34.17.2 sole-keyholder pattern; bypass_actors=[] restored post-merge) |
| **Sprint 6 / F1 sub-phases 1-2** | ✅ shipped 2026-05-15 | (1) PyPI publish aegis-sdk 1.0.0 (closes cosmic-flute task #59). (2) aegis-governance aegis-deploy.yml refactor (PR #178; squash-merge `99dab87`; 6-job pipeline: test→build-candidate→migrate→attest→verify→promote). | aegis-governance v1.2.5 tag (NOT yet deployed to production; dry-run gated) |
| **Sprint 6 / F1 sub-phase 3** | 🟠 EXECUTED-FAILED-GRACEFULLY 2026-05-17 | `workflow_dispatch dry_run=true` from aegis-governance@v1.2.5 (RUN `25980426234`). 4/5 jobs PASS (test + build-candidate + migrate + attest); verify FAILED at actions/checkout with `not our ref` — root cause: aegis-policy reusable workflow used `ref: ${{ github.workflow_sha }}` which resolves to CALLER's SHA in cross-repo workflow_call (per github/gh-aw #24918). promote SKIPPED gracefully fail-closed. Trust spine PROVEN INTACT via local Tier-4e canonical proof with real pinned keys. See cosmic-flute §37.17. | aegis-governance RUN 25980426234 logs |
| **Sprint 6 / F1 sub-phase 3a** | 🟡 in-progress 2026-05-19 (THIS PR) | aegis-policy hotfix: defense-in-depth fix to `aegis-verify-attestation.yml` (job.workflow_sha primary + referenced_workflows API fallback per Microsoft gh-aw PRs + Canonical pattern) + 5 NEW + 1 FLIPPED regression tests + ADR-001 cross-repo lesson + CHANGELOG [1.2.1]. Closes cosmic-flute task #173. | aegis-policy PR #TBD (post-push); merge via §34.17.2 sole-keyholder bypass cycle |
| **Sprint 6 / F1 sub-phase 3b** | ☐ blocked-by 3a | Cross-repo validation via aegis-governance feature branch: bump aegis-deploy.yml SHA pin to 3a merge SHA + `gh workflow run --field dry_run=true`. Expect 5/5 jobs PASS + Tier-4e proof PASS. Discard feature branch after validation. See cosmic-flute §37.18.7. | aegis-governance feature branch (transient) |
| **Sprint 6 / F1 sub-phase 4** | ☐ blocked-by 3b | aegis-governance v1.2.6 PR: bump verify.uses SHA pin to 3a merge SHA + pyproject 1.2.5→1.2.6 + CHANGELOG [1.2.6]. Bundle task #170 (4 sub-phase 2 audit findings) + task #171 (regression guards) if touch-compatible. CLAUDE.md §8 Ask-First gate. Tag v1.2.6 → aegis-deploy.yml fires → full chain runs in non-dry-run mode → production deploys 1.2.4→1.2.6. See cosmic-flute §37.19.2. | aegis-governance v1.2.6 tag |
| **Sprint 6 / F1 sub-phase 5** | ☐ blocked-by 4 | Sprint 6/F1 ship capture: cosmic-flute §37.X with cumulative results across sub-phases 1-4 + lessons learned. Bump memory breadcrumb. Mark task #30 completed. Flip Sprint 6/F2 + Sprint 7 readiness to 🟢 GREEN. | cosmic-flute §37.X new section |
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
        Sprint 5/E1.5 Phase 5 (real keys + policy v2.0.0)
        ✅ aegis-policy@5223f58
                        │
                        ▼
        Sprint 5/E1.5 Phases 6+7+8 (prod redeploy + org-Ruleset + Tier 4e live re-verify)
        ✅ shipped 2026-05-12 — cosmic-flute §32
                        │
        ┌───────────────────────────────────┐
        │ Sprint 5/E2 (✅ shipped)           │
        │ ✅ aegis-policy@19a751e            │
        │ composite action + replay-detection│
        │ closes cosmic-flute #28 + #119     │
        └───────────────┬───────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────┐
        │ Sprint 5/E3 (✅ shipped)           │
        │ ✅ aegis-policy@c34c783            │
        │ reusable workflow (workflow_call) │
        │ closes cosmic-flute #29           │
        │ bundles #129 deferred doc-flips   │
        └───────────────┬───────────────────┘
                        │
                        ▼
                Sprint 6/F1 (aegis-deploy.yml dogfood)
                Sprint 6/F2 (openclaw blue-green dogfood)
                        │
                        ▼
                Sprint 7/G1+G2+G3 (org Ruleset + 20-repo rollout)
```
