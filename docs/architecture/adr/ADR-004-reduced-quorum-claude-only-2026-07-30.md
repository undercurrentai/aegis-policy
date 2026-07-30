# ADR-004 — Reduced-quorum (`claude-only`) auto-approval while the OpenAI lanes are unfunded

**Status:** Accepted 2026-07-30 (Josh, plan approval — the no-spend sweep plan, U1) · **Review by:** 2026-09-28 (+60d)
**Supersedes:** nothing — the full tri-AI quorum remains the DEFAULT; this ADR authorizes a
switchable, dated, reversible reduction.

## Context

The §44 Phase 2 auto-approve aggregator (`.github/workflows/ai-second-review.yml`) requires all
three AI reviewer lanes — gpt-5.4-pro, Codex, Claude — to report clean verdicts before the
`@aegis-auto-reviewer` machine-user posts a binding code-owner approval on ROUTINE
(non-trust-spine, non-self-tune) PRs. The OpenAI platform account is unfunded and there is no
funding planned; both OpenAI lanes die on every run, §54.5 rule 1 (ABSENT → BLOCK) correctly
fail-closes, and every routine PR — down to a docs typo — requires a manual §34.17.2 break-glass
cycle. That is the fail-closed design working as intended, and it has become a standing
operational tax with no risk-reduction return: the blocked PRs get exactly the same single-human
review the break-glass cycle provides anyway.

## Decision

Add a repository variable `AEGIS_REVIEW_QUORUM`. When it holds the EXACT literal `claude-only`:

- the two OpenAI reviewer jobs are skipped cleanly (job-level `if:`; `result == 'skipped'`);
- the aggregator judges routine PRs on the Claude lane alone, under a TIGHTENED envelope:
  - only `APPROVE` passes — a `COMMENT` verdict blocks (under full quorum it passes);
  - only Max Concern `NONE`/`LOW` passes — `MEDIUM` blocks (under full quorum it passes,
    because two other models corroborated overall cleanliness; solo, it routes to a human);
  - the diff must be ≤ 25 files and ≤ 800 changed lines — larger routine PRs stay human-reviewed;
- every decision reason, audit comment, and approval body is tagged `quorum=claude-only` with a
  `[REDUCED QUORUM]` banner and a machine-greppable marker naming this ADR.

Any other value of the variable fails closed — it can never widen approval. A plain typo,
`full`, or unset keeps all three lanes scheduled under full-quorum rules (today's behavior). A
case-variant such as `Claude-Only` splits the switch — GitHub Actions' `!=` compares
case-insensitively, so the OpenAI lanes skip, while the aggregator's case-sensitive `===`
computes `full` — and rule 1 then blocks on the skipped lanes. A mode/lane consistency check
additionally blocks any run where the variable flipped mid-flight. Restoring full quorum is
`gh variable set AEGIS_REVIEW_QUORUM --body full` — a settings flip, no PR.

## Unchanged in every mode (quorum-independent, test-pinned)

Trust-spine carve-out (read from `base.sha`), reviewed-surface ⊆ rule, self-tune D-lock, TOCTOU
head-SHA re-check, PAT + CODEOWNERS layering, fork guards. Trust-spine PRs remain human-only
regardless of quorum. The Claude lane is never skippable and its absence always blocks.

## What is being accepted (stated plainly)

**Three-model error decorrelation collapses to one model inside the tightened envelope.** Rule
2's "any model flags HIGH" tripwire has one wire instead of three; corroborated-dissent and
lone-dissent-noise classification are unreachable; a Claude-specific blind spot (training-
correlated, or a diff crafted against Claude specifically) has no second filter. An Anthropic
outage fails CLOSED (availability loss only). A systematic Claude regression fails OPEN *within*
the APPROVE-only / NONE-LOW-only / small-diff envelope — the tightenings shrink that surface;
they do not recreate independent judgment. That residual is the risk accepted by this ADR.

## Exit condition

Fund the OpenAI platform account, verify both lanes return real verdicts on a probe PR, then
flip the variable to `full` (or delete it). If the review-by date (2026-09-28) passes with the
mode still active, the claude-only branch emits a `core.warning` and the audit banner gains an
"OVERDUE FOR RE-ACCEPTANCE" line — it warns, it does not block (auto-blocking on a date would
silently recreate the break-glass treadmill this ADR exists to relieve).

## Enforcement

`tests/test_workflow_invariants.py::TestReducedQuorumMode` pins: the fail-closed default shapes
on both the job-skip and aggregator sides (incl. the parenthesized fork-guard — GHA `&&`/`||`
precedence), Claude-lane non-skippability, quorum-independence ordering of the shared gates, the
ran-lane-is-never-excused consistency check, and the exact tightening constants (APPROVE-only,
NONE/LOW allowlist, 25/800 caps) so the envelope cannot widen silently.
