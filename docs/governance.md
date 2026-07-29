# Governance

Human-readable summary of how this repo is governed. The machine-readable enforcement lives in [`.github/CODEOWNERS`](../.github/CODEOWNERS), the [PR template](../.github/PULL_REQUEST_TEMPLATE.md), and the workflow files in [`.github/workflows/`](../.github/workflows/).

## CODEOWNERS

Trust-spine owner: the GitHub Team **`@undercurrentai/security-reviewers`** (org team id `18755567`, created 2026-07-29 — the growth path this section previously documented as "not yet implemented" is now half-taken). Sole member today: `@ThermoclineLeviathan`, so every trust-spine change still requires that one human's approval and — since GitHub forbids self-approval — the §34.17.2 break-glass cycle remains the trust-spine merge path until a second human joins the team. The point of the team indirection: adding that second reviewer is a team-membership change in org settings, touching no tracked file, instead of a CODEOWNERS edit that itself costs a break-glass cycle.

**Stricter paths** (functionally equivalent today since the team has a single member; the explicit listing matters when it grows):
- `keys/` — key rotation, trust-root material
- `schema/` — vendored upstream contract
- `policy/` — canonical verifier policy artifact
- `.github/` — CI workflows + repo metadata
- `docs/architecture/` — ADRs

**Remaining growth step**: add a second human to `@undercurrentai/security-reviewers`, then require **2 reviewers** on the strict paths above (`required_approving_review_count: 2`). The single-human-today state is acknowledged and not rationalized as adequate long-term; a second self-owned account was considered and refused (see `docs/roadmap.md`).

**Validity dependency, monitored**: team-based CODEOWNERS lines are only enforced while the team exists and holds write access — both org-settings state outside git. If either lapses, GitHub silently stops enforcing those lines and ownership falls back to the `*` default (which includes the machine-user). The `YAML lint + parse` required check therefore asserts the `codeowners/errors` API returns zero errors on every PR, converting that silent downgrade into a red check.

## PR review requirements

Every PR must:
1. Pass the `lint.yml` workflow (markdownlint + yamllint + parse-smoke on every YAML)
2. Run the `aegis-shadow-eval.yml` workflow (advisory; never blocks)
3. **Pass the `error-class-parity.yml` workflow** if it touches `policy/verifier-policy-v1.yaml` (gating; SDK ↔ policy invariant)
4. Have CODEOWNERS approval (a `@undercurrentai/security-reviewers` member for trust-spine paths; today that is only `@ThermoclineLeviathan`)
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
