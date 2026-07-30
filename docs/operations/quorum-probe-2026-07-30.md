# Reduced-quorum probe — 2026-07-30 (throwaway)

Positive probe for ADR-004 `claude-only` mode (v1.6.0, PR #45). This PR is
closed unmerged once the aggregator's single-lane decision is recorded.

Expected: OpenAI lanes `skipped`, Claude lane reviews, aggregator judges on
the Claude lane alone with the `[REDUCED QUORUM: claude-only]` banner.
