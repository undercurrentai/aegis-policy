# Architecture Decision Records — undercurrentai/aegis-policy

Repo-specific ADR series for the verifier kit + trust roots. Numbered ADR-001 onwards (separate from the `aegis-governance` ADR series, which is at ADR-011 as of 2026-05-09).

| # | Status | Title | Date |
|---|---|---|---|
| [001](ADR-001-repo-trust-model.md) | Accepted | Repo trust model — why this repo exists, CODEOWNERS strictness, org-ruleset enforcement, key-rotation procedure summary | 2026-05-09 |

## Conventions

- Frontmatter: `Status: Proposed | Accepted | Superseded`, `Date: YYYY-MM-DD`
- Status flips to `Accepted` after CODEOWNERS approval on the PR
- Mirror `aegis-governance/docs/architecture/adr/ADR-003` and `ADR-011` formatting (Context / Decision Drivers / Options / Decision / Consequences / References / Changelog)
- New ADRs land via PR with the same gates as any other change to this repo (lint, AEGIS shadow-eval, CODEOWNERS approval)
