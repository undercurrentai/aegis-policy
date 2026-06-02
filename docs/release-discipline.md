# Release Discipline & Consumer-Pinning Contract

> Closes the §48.17 design finding **D5** ("no v1 release-discipline for the 19-consumer
> surface"). This repo is consumed cross-repo by the Sprint 7 portfolio (19 consumers +
> aegis-policy itself). Until now there was no documented policy for *how* consumers should
> pin, *what* a version bump means to them, and *how* releases advance. There are also **zero
> git tags** today — so the only safe pin was a bare commit SHA, and the only unsafe-but-easy
> alternative was `@main` (a moving target with no compatibility contract). This document
> establishes both the policy and the `v1` moving-tag mechanism.

## What consumers actually consume

aegis-policy exposes **two public surfaces**, both invoked cross-repo via `uses:`:

| Surface | Entry point | Shipped | Consumed by |
|---|---|---|---|
| **Verifier kit** | `.github/workflows/aegis-verify-attestation.yml` reusable workflow + `verify-aegis-attestation` composite Action | Sprint 5/E2 + E3 | aegis-governance deploy gate; future deploy-time attestation verification |
| **Enforce substrate** | `.github/workflows/aegis-enforce.yml` reusable workflow | §48 (relocated) + §51 (cross-repo `resolve_callee` fix) | aegis-policy self-dogfood; aegis-governance SP1; all G2/G3 consumers |

The `aegis-gate` composite action (`.github/actions/aegis-gate/action.yml`) is **internal-only** as
of §51 (QG48-D1) — it is an implementation detail of `aegis-enforce.yml`, not a public entry point.
Consumers MUST go through one of the two reusable workflows above; they MUST NOT `uses:` the composite
directly (its bare-minimum defaults diverge from the reusable workflow's CI/CD-domain profile and will
produce different verdicts for the same inputs).

Neither public surface touches production at runtime — verification is offline-by-design (Sprint 4/D2),
and the enforce substrate is advisory in shadow mode. A version bump here changes *consumer CI behavior*,
never the production AEGIS API.

## SemVer → consumer-impact mapping

This repo follows [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html) with
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) (the repo-level `CHANGELOG.md`). The
`policy_version` field of `policy/verifier-policy-v1.yaml` is versioned **separately** in
`policy/CHANGELOG.md` and is NOT the same axis as the repo version — a repo PATCH can ship without a
policy bump, and a policy bump is its own MINOR/MAJOR event on the policy axis.

What each repo-version bump means to a consumer pinning either public surface:

| Bump | Examples | Consumer impact | Safe to track via `@v1`? |
|---|---|---|---|
| **PATCH** (`1.2.x`) | hardening, docs, internal refactor, workflow comment fix, dangling-ref fix | None — inputs/outputs/check-name unchanged | ✅ yes |
| **MINOR** (`1.x.0`) | new **optional** workflow input, new output, new capability with backward-compatible defaults | None for existing callers; new opt-in surface available | ✅ yes |
| **MAJOR** (`x.0.0`) | removed/renamed input, changed default that flips a verdict, changed resolved check-name string, removed output | **Breaking** — caller must migrate before adopting | ❌ no — `v1` does NOT auto-advance to `v2` |

The resolved required-check string (`aegis-gate / AEGIS Governance Gate`) is a **MAJOR-gated contract**:
changing it would break every org-Ruleset that targets it (id `17101026` per §48 SP5) and is therefore
a v2 event, never a v1 PATCH/MINOR.

## Pinning options (recommended → forbidden)

| Pin | Form | Immutable? | Auto-updates? | When to use |
|---|---|---|---|---|
| **SHA** (RECOMMENDED) | `@2163336350f879aa0bc121e28418f4f331bbe075` | ✅ byte-immutable | ❌ manual bump | Default for production consumers. Max supply-chain safety. Pair with Dependabot `github-actions` ecosystem updates (per §47 PR-A precedent). |
| **`v1` moving tag** (CONVENIENCE) | `@v1` | ❌ moves within v1 | ✅ within v1 (PATCH+MINOR) | Consumers who want backward-compatible auto-updates without per-release PRs and who'd otherwise reach for `@main`. Trusts the moving tag + this repo's MAJOR-gating discipline. |
| **`@main`** (FORBIDDEN) | `@main` | ❌ moves on every commit | ✅ everything incl. breaking | Never. No compatibility contract; a mid-flight commit can break the consumer with no warning. The §48.16 PUBLIC→PRIVATE failure was surfaced exactly because there was no pin discipline. |

**Why SHA stays the recommended default** even though `v1` is more convenient: the 2026 supply-chain
posture (post-Trivy May 2026; CNCF + GitHub Security Lab guidance per cosmic-flute §47.1) treats SHA-pin
as the baseline for third-party actions, with automated bumps (Dependabot) making it sustainable. `v1`
is offered as the *strictly-better-than-`@main`* option, not as a replacement for SHA-pinning a
production gate.

## The `v1` moving-tag contract

- `v1` always points at the **latest released `1.x.y` commit on `main`** that has passed the full
  ship gate (CI green + AEGIS Stage-2 + CHANGELOG entry + §34.17.2 sole-keyholder merge).
- `v1` advances **only** for PATCH and MINOR releases. It is NEVER moved to a commit that introduces a
  breaking change — that commit gets `v2.0.0` + a new `v2` moving tag, and `v1` freezes at the last
  backward-compatible `1.x.y`.
- `v1` is a **force-updated lightweight tag** (`git tag -f v1 <release-sha>`), not an annotated release.
  Per-release immutable tags (`v1.2.6`, `v1.3.0`, …) are annotated and never moved — those are the
  audit anchors; `v1` is the convenience pointer.

## Release procedure (per §34.17.2 sole-keyholder discipline)

A release is a `main` commit that (1) bumps the repo version in `CHANGELOG.md`, (2) passes CI + the
`aegis-shadow-eval` advisory gate, (3) carries an AEGIS Stage-2 decision_id in the PR body, and (4)
lands via the documented sole-keyholder bypass cycle on org-Ruleset `16294975` with `bypass_actors=[]`
preserved (snapshot `[]` → full-PUT round-trip add `OrganizationAdmin` → admin-squash-merge → full-PUT
restore `[]` → re-verify `[]`; partial-PUT 422s as of §48.16.5).

After the release merges:

```bash
RELEASE_SHA=$(git rev-parse origin/main)        # the squash-merge commit
VERSION=1.2.6                                    # from the CHANGELOG entry just shipped

# 1. Immutable per-release annotated tag (audit anchor; never moved)
git tag -a "v${VERSION}" "${RELEASE_SHA}" -m "aegis-policy v${VERSION}"
git push origin "v${VERSION}"

# 2. Advance the v1 moving tag — ONLY for PATCH/MINOR (skip on MAJOR; v2 gets its own tag)
git tag -f v1 "${RELEASE_SHA}"
git push origin v1 --force
```

The first `v1` tag is established at the §51 ship (it points at the §51 merge SHA — the first commit
with the full contract-hardened public surface: composite marked internal-only, cross-repo `resolve_callee`
fix, and the D1–D8 contract-coherence findings closed).

## Growth path (single-keyholder reality)

Today `@ThermoclineLeviathan` is the sole keyholder and runs every release manually. When a second
engineer joins (per `docs/governance.md` growth path), release-tagging can be automated via a
`release-please`-style workflow gated on the same `@undercurrentai/security-reviewers` 2-of-N review —
but the SHA-pin-recommended default and the MAJOR-gated `v1` contract above do not change.

## References

- cosmic-flute §48.17 D5 (the finding this closes) · §51 (the contract-hardening ship) · §47.1 (SHA-pin
  supply-chain posture) · §48.16.5 (full-PUT bypass-cycle mechanism)
- `docs/governance.md` — PR review + sole-keyholder merge discipline
- `CHANGELOG.md` (repo version axis) · `policy/CHANGELOG.md` (policy_version axis)
- [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html) · [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
