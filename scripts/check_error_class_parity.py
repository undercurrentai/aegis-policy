"""Check error_class parity between aegis-policy and the aegis-sdk[verify] SDK.

Loads `policy/verifier-policy-v1.yaml fail_closed_on` (snake_case canonical
names), translates each entry to its PascalCase SDK error_class string,
and compares against the actual error_class strings the SDK's
`verify_attestation_locally()` function returns (extracted via AST walk over
the vendored source at `scripts/_verify_local_vendored.py`).

Fails (exit 1) if either side has a member the other lacks. This is the CI
gate that prevents silent drift between the SDK error_class taxonomy and
the policy artifact's fail-closed taxonomy — without it, a SDK release that
adds (or removes) an error_class would silently break consumers verifying
against an unchanged policy.

Closes the manual-audit gap from cosmic-flute §26.11 step 4.

**Vendored source rationale**: aegis-governance is private (BSL-1.1) and
aegis-governance>=0.5.0 is not yet on PyPI (latest published: 0.4.1). We
cannot `pip install aegis-governance[verify]>=0.6.1` from any source the CI
runner can reach without secrets infrastructure. So we vendor
`_verify_local.py` verbatim into `scripts/_verify_local_vendored.py` and
read it directly. Drift is caught at refresh time (manual SHA bump in the
vendored file's header + policy/CHANGELOG.md); the alternative was carrying
a PAT secret + Git-installer in CI which is more complex than the drift risk.

Usage:
    pip install -r requirements-dev.txt
    python scripts/check_error_class_parity.py

Exit codes:
    0 — parity holds
    1 — parity violated (output describes which side has extras)
    2 — execution error (yaml parse failed, vendored source missing, etc.)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = REPO_ROOT / "policy" / "verifier-policy-v1.yaml"
VENDORED_SDK_PATH = REPO_ROOT / "scripts" / "_verify_local_vendored.py"


def snake_to_pascal(snake: str) -> str:
    """Translate a fail_closed_on snake_case entry to its SDK PascalCase error_class.

    Special-cases the two non-standard segments per ADR-011:
      ed25519 -> Ed25519 (initial capital + lowercase 'd')
      mldsa   -> MLDSA   (all caps)

    All other segments use simple title-case.
    """
    parts = snake.split("_")
    out: list[str] = []
    for p in parts:
        if p == "ed25519":
            out.append("Ed25519")
        elif p == "mldsa":
            out.append("MLDSA")
        else:
            out.append(p.capitalize())
    return "Attestation" + "".join(out)


def load_expected_from_policy() -> set[str]:
    """Read policy/verifier-policy-v1.yaml and translate fail_closed_on -> SDK names."""
    if not POLICY_PATH.exists():
        print(f"ERROR: policy file not found at {POLICY_PATH}", file=sys.stderr)
        sys.exit(2)
    try:
        data = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"ERROR: failed to parse {POLICY_PATH}: {e}", file=sys.stderr)
        sys.exit(2)
    fail_closed_on = data.get("fail_closed_on")
    if not isinstance(fail_closed_on, list):
        print(
            f"ERROR: policy fail_closed_on is missing or not a list (got {type(fail_closed_on).__name__})",
            file=sys.stderr,
        )
        sys.exit(2)
    expected: set[str] = set()
    for entry in fail_closed_on:
        if not isinstance(entry, str):
            print(f"ERROR: fail_closed_on contains non-string entry: {entry!r}", file=sys.stderr)
            sys.exit(2)
        expected.add(snake_to_pascal(entry))
    return expected


def load_actual_from_sdk() -> set[str]:
    """AST-extract every error_class string returned by the vendored SDK source.

    Walks the AST of `scripts/_verify_local_vendored.py` looking for
    `return (..., "AttestationXxx")` tuple returns (the SDK's contract is
    `tuple[bool, str | None]` per `_verify_local.py:191`). AST-based rather
    than regex so docstring placeholder strings (e.g., the literal
    "AttestationXxxMismatch" used as a meta-syntactic example in the verifier's
    docstring) are ignored — only strings actually returned at runtime count.

    Reads from the vendored copy at `scripts/_verify_local_vendored.py` rather
    than `from aegis import _verify_local` because aegis-governance>=0.5.0 is
    not yet on PyPI and the source repo is private. See module docstring.
    """
    if not VENDORED_SDK_PATH.exists():
        print(
            f"ERROR: vendored SDK source not found at {VENDORED_SDK_PATH}",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        source = VENDORED_SDK_PATH.read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERROR: failed to read vendored SDK source: {e}", file=sys.stderr)
        sys.exit(2)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(
            f"ERROR: failed to AST-parse vendored SDK source: {e}",
            file=sys.stderr,
        )
        sys.exit(2)

    verify_fn: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "verify_attestation_locally":
            verify_fn = node
            break

    if verify_fn is None:
        print(
            "ERROR: verify_attestation_locally() not found in vendored SDK source",
            file=sys.stderr,
        )
        sys.exit(2)

    actual: set[str] = set()
    for node in ast.walk(verify_fn):
        # Look for `return (False, "AttestationXxx")` and `return (True, None)`
        # patterns. Only tuples; skip plain `return None` or single-value returns.
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple):
            for elt in node.value.elts:
                if (
                    isinstance(elt, ast.Constant)
                    and isinstance(elt.value, str)
                    and elt.value.startswith("Attestation")
                ):
                    actual.add(elt.value)

    if not actual:
        print(
            "ERROR: zero Attestation* strings found in vendored SDK return tuples — "
            "AST walk broken or SDK API changed",
            file=sys.stderr,
        )
        sys.exit(2)
    return actual


def main() -> int:
    expected = load_expected_from_policy()
    actual = load_actual_from_sdk()

    only_in_policy = sorted(expected - actual)
    only_in_sdk = sorted(actual - expected)

    print(f"Policy fail_closed_on entries (translated): {len(expected)}")
    print(f"SDK error_class strings: {len(actual)}")

    if not only_in_policy and not only_in_sdk:
        print("✓ PARITY HOLDS — every SDK error_class is in policy fail_closed_on, and vice versa.")
        return 0

    print()
    print("✗ PARITY VIOLATED")
    if only_in_policy:
        print()
        print(f"Entries in policy but NOT emitted by SDK ({len(only_in_policy)}):")
        for name in only_in_policy:
            print(f"  - {name}")
        print(
            "  -> Either remove from policy/verifier-policy-v1.yaml fail_closed_on,"
            " or update the SDK to emit this error_class."
        )
    if only_in_sdk:
        print()
        print(f"Error classes emitted by SDK but NOT in policy ({len(only_in_sdk)}):")
        for name in only_in_sdk:
            print(f"  - {name}")
        print(
            "  -> Add to policy/verifier-policy-v1.yaml fail_closed_on (snake_case translation)"
            " and bump policy_version + policy/CHANGELOG.md."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
