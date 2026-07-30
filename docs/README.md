# aegis-policy docs

| Path | Purpose |
|---|---|
| [`architecture/adr/README.md`](architecture/adr/README.md) | ADR index for this repo |
| [`architecture/adr/ADR-001-repo-trust-model.md`](architecture/adr/ADR-001-repo-trust-model.md) | Trust-model ADR — why this repo exists, CODEOWNERS strictness, org-ruleset enforcement, key-rotation procedure summary |
| [`governance.md`](governance.md) | Human-readable summary of CODEOWNERS + PR review requirements + AEGIS shadow-eval gate |
| [`release-discipline.md`](release-discipline.md) | Consumer-pinning contract + SemVer→impact mapping + `v1` moving-tag plan (closes §48.17 D5) |
| [`key-rotation-runbook.md`](key-rotation-runbook.md) | Full procedure for rotating the Ed25519 + ML-DSA-65 keys (routine + compromise paths) |
| [`operations/trust-spine-break-glass.md`](operations/trust-spine-break-glass.md) | The §34.17.2 sole-keyholder break-glass merge procedure |
| [`roadmap.md`](roadmap.md) | Open governance items (second code owner, verifier-kit promotion, consumer SDK-default bump) + shipped-sprint history |

For the canonical predicate schema + verifier policy, see [`../schema/`](../schema/) and [`../policy/`](../policy/) at the repo root.
