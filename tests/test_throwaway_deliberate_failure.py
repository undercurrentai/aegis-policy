"""Throwaway probe 2 (PR #38): a red Test suite must BLOCK the merge.

Deleted with the PR — never merged.
"""


def test_deliberately_fails_to_prove_the_gate_blocks():
    assert False, "deliberate failure: proving 'Test suite' is now a blocking required check"
