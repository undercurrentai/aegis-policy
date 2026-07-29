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
| **Sprint 6 / F1 sub-phase 3a** | ✅ shipped 2026-05-19 (commit `c2ce026`) | aegis-policy hotfix: defense-in-depth fix to `aegis-verify-attestation.yml` (job.workflow_sha primary + referenced_workflows API fallback per Microsoft gh-aw PRs + Canonical pattern) + 5 NEW + 1 FLIPPED regression tests + ADR-001 cross-repo lesson + CHANGELOG [1.2.1]. Closes cosmic-flute task #173. | PR #11 (squash-merged via admin per cosmic-flute §34.17.2 sole-keyholder pattern; bypass_actors=[] restored post-merge) |
| **QG-§37.18 post-ship audit** | ✅ shipped 2026-05-19 (commit `cded778`) | Post-sub-phase-3a /quality-gate exhaustive audit on aegis-policy@c2ce026. Phase 2 surfaced 24 findings; Phase 3 surfaced 10 additional probes; Phase 7 produced v1.2.2 patch consolidating hardenings (multi-match dedup logic + anchored SELF_REGEX + 6 regression-test refinements). Closes accepted-findings entries in `.quality-gate/accepted-findings.jsonl` rows 1-5. Bundles 8 LOW × C1/C2/C3 deferrals into Sprint 7/G1 task #185. | PR #12 (squash-merged via admin per cosmic-flute §34.17.2 sole-keyholder pattern; cosmic-flute §37.18.16) |
| **Sprint 6 / F1 sub-phase 3b** | ✅ validated 2026-05-19 (aegis-governance RUN `26102961343`) | Cross-repo validation via aegis-governance feature branch: bumped aegis-deploy.yml SHA pin from `5b3e2c0` to `c2ce026` + `gh workflow run --field dry_run=true`. All 5 jobs PASS (test + build-candidate + migrate + attest + **verify ✅ 1m23s**); promote SKIPPED gracefully per dry_run gate. A6 Tier-4e canonical proof PASS valid=True with REAL pinned keys for decision_id `9a181766-…`. Feature branch discarded post-validation. See cosmic-flute §37.18.15. | aegis-governance feature branch (transient; deleted post-validation) |
| **Sprint 6 / F1 sub-phase 4** | ✅ shipped 2026-05-19 (aegis-governance v1.2.6 production deploy) | aegis-governance v1.2.6 PR #182 (squash-merge `8aa151d`): bumped verify.uses SHA pin `5b3e2c0` → `cded778` + workflow-level `actions: read` perm + pyproject 1.2.5 → 1.2.6 + CHANGELOG [1.2.6]. Bundled task #170 (4 sub-phase 2 audit findings: GAT-1 runbook + GAT-2 LIKE-pattern fix + others) + task #171 (regression guards). CLAUDE.md §8 Ask-First gate cleared via plan-mode. Tag v1.2.6 → aegis-deploy.yml fires → 6/6 jobs PASS → production aegis-api Cloud Run transitioned v1.2.4 → v1.2.6 (first non-dry-run attested production deploy; decision_id `52689bf3-…`). AEGIS Stage-2 PR-gate decision_id `8e6a4573-…` (PAUSE → override per §28.5.1 routine-deploy precedent). See cosmic-flute §37.21. | aegis-governance v1.2.6 tag → Cloud Run revision atomic-shifted 100% to v1.2.6 |
| **Sprint 6 / F1 sub-phase 5** | ✅ shipped 2026-05-19 (cosmic-flute §37.21 ship capture) | Sprint 6/F1 SHIP COMPLETE — cosmic-flute §37.21 captures cumulative results across sub-phases 1-4 + lessons learned. Memory breadcrumb bumped to "Sprints 1-6/F1 of 7 SHIPPED". Mark cosmic-flute tasks #30 + #170 + #171 + #174 completed. Sprint 6/F2 + Sprint 7/G1-G3 readiness flipped 🟢 GREEN UNBLOCKED at protocol-correctness layer. | cosmic-flute §37.21 — Sprint 6/F1 SHIPPED capture |
| **§38 (post-ship CTR-5/U3 closure + forensic-audit chain)** | ✅ shipped 2026-05-21 (aegis-governance v1.2.7 production deploy) | Cumulative 3-PR ship cycle on aegis-governance: PR #183 (`c570505`) primary §38 + PR #184 (`25420ca`) PyPI 1.1.0→1.1.1 yanked-collision hotfix + PR #185 (`f012a33`) Attest job step-order hotfix. Tag v1.2.7 → production transitioned v1.2.6 → v1.2.7. First v1.2.7 production decision_id `302693ce-…`; Tier-4e canonical proof PASS valid=True with REAL pinned keys from aegis-policy@cded778. ADR-013 forensic-audit chain via `aegis_evaluate_decision_id` DB column (Option D — predicate UNCHANGED + envelope wire format BYTE-IDENTICAL with v1.2.6). aegis-sdk 1.1.1 LIVE on PyPI (post yanked-1.1.0-collision PR #184 remediation per §37.14.7 release chain). §17 Critical 3 invariant `bypass_actors=[]` preserved across 9 cumulative sole-keyholder bypass cycles. aegis-policy main UNCHANGED at `cded778` (§38 D2-defer; Sprint 7/G1 task #185 picks up policy `informational_predicate_fields` update). Closes cosmic-flute tasks #196 + #197. See cosmic-flute §38.13. | aegis-governance v1.2.7 tag → Cloud Run revision atomic-shifted 100% to v1.2.7 |
| **Sprint 6 / F2** | 🟢 GREEN UNBLOCKED — planned | `openclaw-operator-os/scripts/blue-green-deploy.sh` integration (dogfood across 3 substrates per cosmic-flute §11.7). Unblocked at protocol-correctness layer via §38 Option D architecture. | Separate plan + PR (on `openclaw-operator-os`); cosmic-flute task #31 |
| **Sprint 7 / G1 task #185 (verifier-kit + tri-AI hardening bundle)** | ✅ shipped 2026-05-26 (commit `5368700` + cycle-1 fix `d9056ef`) | 11-item bundle on aegis-policy closing all §37.18.16 + §44.20.3 P1.5 baseline #1 + §44.20.10.2 P1.5 baseline #2 deferred findings. PR #16 admin-squash-merged via **16th cumulative §34.17.2 sole-keyholder bypass cycle** (`5368700`); CI 7/7 GREEN on first push; AEGIS Stage-2 decision_id `78eab9b6-…` PAUSE 6/6 gates PASSED clean (no override required — first §45-class ship to clear novelty cleanly). 5 atomic commits, ~906 net LOC. Layers shipped: C1 dual-checkout BASE/HEAD + C2 comment-pipeline lockdown (NEW-H1 + NEW-H2 closure via artifact-based Claude verdict pipeline) + C3 verifier-kit semantics + Node test harness (F2.2 + U1+U2 + U9/F1.3 closure) + C4 Codex scope-gating + C5 stale-SHA + G3 + G4 truncation fail-closed. **Post-ship cycle-1 fix**: PR #17 admin-squash-merged via **17th cumulative bypass cycle** (`d9056ef`); cycle-1 caught a §45-introduced regression (claude-review Enforce verdict missing empty-diff skip clause) via dual-source Codex Lane A + Claude Lane B Agent 1 confirmation (MEDIUM/C3); AEGIS decision_id `84619c25-…` PAUSE 6/6 gates PASSED clean (Risk DECREASED Δ=-0.25). 12th historical scope-drift instance per §43.11 remediation-introduced sub-class. /quality-gate Phase 2 cycle-2 verification: 0/0 EXIT_CLEAN across 2 partitions. CHANGELOG [1.2.4]. See cosmic-flute §45 + §45.13 + §45.14. | aegis-policy v1.2.4 |
| **Sprint 7 / G1 §48 (SP1-SP6 relocation pivot)** | ✅ shipped 2026-05-31 (aegis-policy `54e4229` PR #20; aegis-governance `dd64b90`) | Relocated the §48 enforce substrate (`aegis-enforce.yml` reusable workflow + `aegis-gate` composite action) from PRIVATE aegis-governance to PUBLIC aegis-policy — root cause: a PUBLIC caller repo cannot invoke a PRIVATE repo's reusable workflow (GitHub platform restriction). Both source repos now consume the substrate LOCALLY via `uses: ./.github/workflows/aegis-enforce.yml`. SP4 created custom org property `aegis-enforce-mode` (`shadow`/`enforce`/`disabled`); SP5 created NEW org-Ruleset `aegis-enforce-required-check` (id `17101026`; `bypass_actors=[]`; targets `repository_property aegis-enforce-mode ∈ [shadow, enforce]`; sole required check `aegis-gate / AEGIS Governance Gate`); SP6 set both aegis-policy + aegis-governance to `shadow`. 29th cumulative §34.17.2 sole-keyholder bypass cycle (16294975 `bypass_actors=[]` preserved). Cross-repo repoint of aegis-governance (follow-up a) + org-allowlist revert (b.2) DEFERRED as a G2 prerequisite — blocked on the cross-repo `./` action-resolution fix (caught via closed PR #196; see cosmic-flute §48.16.3). | aegis-policy `54e4229` (PR #20); org-Ruleset `17101026`; cosmic-flute §48.16 |
| **Sprint 7 / G1 task #32 (org-Ruleset 19-repo expansion)** | 🟡 PARTIAL — SP1-SP6 shipped 2026-05-31 (see §48 row above: substrate + custom property + ruleset `17101026` + shadow self-dogfood on the 2 source repos); 19-repo expansion (G2/G3) pending | Org-level GitHub Ruleset for required `aegis-attestation-verified` status check across all 19 (now 20) portfolio repos. Admin-level operation. NOTE: an attestation-stack-internal Ruleset (`aegis-attestation-required-checks`, id `16294975`) targeting `aegis-*` repos was already created during Sprint 5/E1.5 Phase 7 (2026-05-12); Sprint 7/G1 expands enforcement to the full 19-repo portfolio (`aegis-gtm`, `undercurrent-core`, `LIBERTAS-*`, etc.). | Org settings change; cosmic-flute task #32 + §48.16 |
| **Sprint 7 / G2** | 🟢 GREEN UNBLOCKED — planned | `aegis-gtm` pilot rollout — first non-aegis-governance consumer. Validates verifier-kit ergonomics for the typical Vercel-deployed website. | Separate plan + PR (on `aegis-gtm`); cosmic-flute task #33 |
| **Sprint 7 / G3** | 🟢 GREEN UNBLOCKED — planned | Roll out to remaining 18 production-bound repos. Tracked via Linear when Step 2 of the operator-OS plan wires Linear webhook. | Linear epic per repo; cosmic-flute task #34 |

## Open — governance

### Second trust-spine code owner

**Status:** 🔴 OPEN — the durable fix for the §34.17.2 sole-keyholder cycle.

`.github/CODEOWNERS` assigns every trust-spine path (`.github/`, `keys/`, `schema/`, `policy/`,
`scripts/`, `actions/`, `docs/architecture/`) solely to `@ThermoclineLeviathan`. All three org
rulesets require code-owner review, `aegis-attestation-required-checks` (`16294975`) has
`bypass_actors=[]`, and the `@aegis-auto-reviewer` aggregator is designed never to auto-approve a
trust-spine change. GitHub forbids self-approval, so **the sole code owner cannot merge
trust-spine work in-band** — which is why the ROADMAP records 29+ cumulative bypass cycles.

The interim procedure is now written down at `docs/operations/trust-spine-break-glass.md`. The
durable fix is a second human reviewer, or a GitHub Team as code owner so adding someone later
needs no CODEOWNERS edit.

**Ordering trap:** editing `CODEOWNERS` is *itself* a trust-spine change, so the first such edit
still requires one final break-glass cycle.

**Tracking:** `docs/operations/trust-spine-break-glass.md`; cosmic-flute §34.17.2

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
        ┌───────────────────────────────────────┐
        │ Sprint 6/F1 sub-phase 3a (✅ shipped)  │
        │ ✅ aegis-policy@c2ce026                │
        │ cross-repo workflow_call self-checkout │
        │ defense-in-depth fix                   │
        │ closes cosmic-flute #173               │
        │ (sub-phase 3b validated 2026-05-19    │
        │  via aegis-governance feature branch) │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │ QG-§37.18 post-ship audit (✅ shipped) │
        │ ✅ aegis-policy@cded778                │
        │ v1.2.2 patch — multi-match dedup +    │
        │ anchored SELF_REGEX + regression-test │
        │ refinements + 8 LOW deferrals → #185  │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │ Sprint 6/F1 sub-phase 4 (✅ shipped)   │
        │ ✅ aegis-governance@8aa151d (v1.2.6)   │
        │ first non-dry-run production deploy   │
        │ decision_id 52689bf3-…                │
        │ closes cosmic-flute #30+#170+#171+#174│
        │ Sprint 6/F1 SHIP COMPLETE — §37.21    │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │ §38 forensic-audit chain (✅ shipped)  │
        │ ✅ aegis-governance@f012a33 (v1.2.7)   │
        │ ADR-013 + aegis_evaluate_decision_id  │
        │ Option D — predicate UNCHANGED        │
        │ envelope wire format BYTE-IDENTICAL   │
        │ aegis-sdk 1.1.1 on PyPI               │
        │ closes cosmic-flute #196 + #197       │
        │ first v1.2.7 decision_id 302693ce-…  │
        │ aegis-policy main UNCHANGED at cded778│
        │ (§38 D2-defer; Sprint 7/G1 #185 picks │
        │  up informational_predicate_fields)   │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │ Sprint 7/G1 task #185 (✅ shipped)     │
        │ ✅ aegis-policy@5368700 + d9056ef      │
        │ verifier-kit + tri-AI hardening bundle│
        │ 11 items closed (C1+C2+C3+C4+C5)      │
        │ 16th + 17th sole-keyholder bypass cycles│
        │ /quality-gate cycle-2: 0/0 EXIT_CLEAN │
        │ closes cosmic-flute #185               │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        🟢 Sprint 6/F2 (openclaw blue-green dogfood)
        🟢 Sprint 7/G1 task #32 (org Ruleset 19-repo rollout — admin op)
        🟢 Sprint 7/G2 (aegis-gtm pilot)
        🟢 Sprint 7/G3 (18-repo Linear rollout)
        ALL UNBLOCKED at architectural-contract layer per §38.13.7 + §45.13
```
