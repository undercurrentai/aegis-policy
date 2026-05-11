# Architecture Decision Records — undercurrentai/aegis-policy

Repo-specific ADR series for the verifier kit + trust roots. Numbered ADR-001 onwards (separate from the `aegis-governance` ADR series, which is at ADR-011 as of 2026-05-09).

| # | Status | Title | Date |
|---|---|---|---|
| [001](ADR-001-repo-trust-model.md) | Accepted | Repo trust model — why this repo exists, CODEOWNERS strictness, org-ruleset enforcement, key-rotation procedure summary | 2026-05-09 |
| [002](ADR-002-key-ceremony-2026-05-10.md) | Accepted | Sprint 5/E1.5 key ceremony — captured Ed25519 + ML-DSA-65 fingerprints; SOFTWARE-protection acceptance; AEGIS Stage-2 override per §28.5.1 | 2026-05-10 |
| [003](ADR-003-ml-dsa-44-to-65-migration.md) | Accepted | ML-DSA-44 → ML-DSA-65 algorithm migration (downstream of upstream ADR-012); aegis-policy v1.0.0 → v2.0.0 BREAKING; vendored verifier re-vendored from aegis-governance@7e422b2 | 2026-05-10 |

## Conventions

- Frontmatter: `Status: Proposed | Accepted | Superseded`, `Date: YYYY-MM-DD`
- Status flips to `Accepted` after CODEOWNERS approval on the PR
- Mirror `aegis-governance/docs/architecture/adr/ADR-003` and `ADR-011` formatting (Context / Decision Drivers / Options / Decision / Consequences / References / Changelog)
- New ADRs land via PR with the same gates as any other change to this repo (lint, AEGIS shadow-eval, CODEOWNERS approval)
