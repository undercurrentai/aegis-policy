## Summary

<1-3 sentences describing the change and why it's needed>

## Change Class

- [ ] **A** — Documentation only, no behavior change
- [ ] **B** — Behavior-preserving (refactor, defensive coding, comment fix)
- [ ] **C** — Behavioral (new feature, contract change, schema change)
- [ ] **D** — Breaking (API surface removed/changed; SemVer MAJOR bump)

## NIST 800-53r5 Controls

List all controls touched (e.g. AC-3, AC-4, AU-10, CM-3, CM-6, SC-13, SI-7, SR-4):

`<controls>`

## Verifier Policy Impact (high-trust paths)

If this PR touches `keys/`, `schema/`, `policy/`, or `.github/workflows/`:

- [ ] CODEOWNERS approval present (`@ThermoclineLeviathan`)
- [ ] `policy/verifier-policy-v1.yaml policy_version` bumped if `fail_closed_on` / `required_*` fields changed
- [ ] `policy/CHANGELOG.md` entry added if `policy/` changed
- [ ] `schema/PROVENANCE.md` SHA updated if `schema/` changed (vendoring refresh)
- [ ] `keys/` rotation: ceremony per `docs/key-rotation-runbook.md` followed
- [ ] Consumer impact: any downstream repos pinned to a SHA that needs updating?

## Risk register / Impact

- **Blast radius**: <repos / surfaces affected — note all 19 portfolio consumers if changing required_* or fail_closed_on>
- **Reversibility**: <git revert sufficient? config flip needed?>
- **Determinism**: <deterministic? non-deterministic factors documented?>
- **Secrets / Egress**: <any new secrets, external network calls?>

## AI Assistance Disclosure

- [ ] AI-assisted (Co-Authored-By trailer present)
- [ ] AI-only (no human review yet)
- [ ] Human-only

If AI-assisted, AEGIS Stage-2 decision_id: `<uuid or N/A>`

## Test Plan

- [ ] All YAMLs parse cleanly (`python -c 'import yaml; yaml.safe_load(open(...))'` for each touched file)
- [ ] `lint.yml` workflow green
- [ ] `aegis-shadow-eval.yml` workflow runs (advisory; never blocks)
- [ ] **`error-class-parity.yml` workflow green** — SDK ↔ policy parity invariant holds
- [ ] CODEOWNERS protects intended paths (≥ 5)
- [ ] /quality-gate exhaustive 9-phase clean (where applicable)

## References

- Cosmic-flute plan: `~/.claude/plans/let-s-plan-this-cosmic-flute.md`
- Predecessor PR / Sprint:
- ADR (if applicable):
