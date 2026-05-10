# Governance

Human-readable summary of how this repo is governed. The machine-readable enforcement lives in [`.github/CODEOWNERS`](../.github/CODEOWNERS), the [PR template](../.github/PULL_REQUEST_TEMPLATE.md), and the workflow files in [`.github/workflows/`](../.github/workflows/).

## CODEOWNERS

Single owner today: `@ThermoclineLeviathan`. Every change to every path requires owner approval — no exceptions.

**Stricter paths** (functionally equivalent today since there's a single owner; the explicit listing matters when the team grows):
- `keys/` — key rotation, trust-root material
- `schema/` — vendored upstream contract
- `policy/` — canonical verifier policy artifact
- `.github/` — CI workflows + repo metadata
- `docs/architecture/` — ADRs

**Growth path** (documented commitment, not yet implemented): when a second engineer joins, replace the single owner with a `@undercurrentai/security-reviewers` 2-of-N team and require **2 reviewers** on the strict paths above. The single-owner-today state is acknowledged and not rationalized as adequate long-term.

## PR review requirements

Every PR must:
1. Pass the `lint.yml` workflow (markdownlint + yamllint + parse-smoke on every YAML)
2. Run the `aegis-shadow-eval.yml` workflow (advisory; never blocks)
3. **Pass the `error-class-parity.yml` workflow** if it touches `policy/verifier-policy-v1.yaml` (gating; SDK ↔ policy invariant)
4. Have CODEOWNERS approval (`@ThermoclineLeviathan`)
5. Have an AEGIS Stage-2 decision_id captured in the PR body's NIST AI Disclosure section (when AI-assisted)
6. Use squash-merge (linear history; matches portfolio convention)

## AEGIS Stage-2 self-eval gate

Every PR runs the AEGIS shadow-eval workflow which calls `aegis_evaluate_proposal` against `https://aegis-api-980022636831.us-central1.run.app`. The result is **advisory only** — it captures a decision_id for audit trail but does not block merge. This implements self-dogfood: aegis-policy uses AEGIS to gate aegis-policy.

For high-impact changes (key rotation, schema bumps, contract tightening) the recommendation is to ALSO submit a manual `mcp__aegis-governance__aegis_evaluate_proposal` call with derived scores **before** opening the PR, capture the decision_id, paste it into the PR body. The shadow-eval workflow's automatic submission is a safety net, not the primary gate.

## Org-level GitHub Ruleset (Sprint 5/E1.5)

Deferred to E1.5 admin-level operation. Will require the following status checks before merge to `main`:
- `lint.yml`
- `aegis-shadow-eval.yml` (advisory; status is "success" because of `continue-on-error: true`)
- `error-class-parity.yml` (gating)
- CODEOWNERS approval (1 reviewer today; 2 when team grows)

No bypass actors (admins included; the sole owner does NOT bypass own gates). Linear-history enforced (squash-merge only).

## What lives elsewhere

- **Predicate schema source-of-truth**: `aegis-governance/schema/attestation_predicate_v1.yaml` (BSL-1.1 private repo). This repo vendors a verbatim copy in `schema/`.
- **SDK error_class taxonomy source-of-truth**: `aegis-governance/aegis-sdk/src/aegis/_verify_local.py` (Apache-2.0). The wheel will be distributed via PyPI as `aegis-governance[verify]` once `0.6.1+` is published; until then, latest on PyPI is `0.4.1` (pre-D1/D2). Because `aegis-governance` source is private (BSL-1.1) and the `>=0.5.0` line is not yet on PyPI, the verifier source is **vendored verbatim** into `scripts/_verify_local_vendored.py` (with source-SHA pinned in the file's header). The `error-class-parity.yml` workflow AST-walks the vendored copy on every PR; SDK ↔ vendored-copy drift is caught at refresh time per the procedure in `policy/CHANGELOG.md` and the `_verify_local_vendored.py` header.
- **AEGIS API server**: `https://aegis-api-980022636831.us-central1.run.app` (proprietary SaaS). Used by `aegis-shadow-eval.yml` for governance dogfood; never used in the verifier code path itself (verification is offline by design per Sprint 4/D2).
