"""Check error_class parity between aegis-policy and the aegis-sdk[verify] SDK.

Loads `policy/verifier-policy-v1.yaml fail_closed_on` (snake_case canonical
names), translates each entry to its PascalCase SDK error_class string,
and compares against the actual error_class strings emitted by the SDK's
`verify_attestation_locally()` function (parsed via regex from the installed
`aegis._verify_local` module source).

Fails (exit 1) if either side has a member the other lacks. This is the CI
gate that prevents silent drift between the SDK error_class taxonomy and
the policy artifact's fail-closed taxonomy — without it, a SDK release that
adds (or removes) an error_class would silently break consumers verifying
against an unchanged policy.

Closes the manual-audit gap from cosmic-flute §26.11 step 4.

Usage:
    pip install -r requirements-dev.txt
    python scripts/check_error_class_parity.py

Exit codes:
    0 — parity holds
    1 — parity violated (output describes which side has extras)
    2 — execution error (yaml parse failed, SDK import failed, etc.)
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import yaml

POLICY_PATH = Path(__file__).resolve().parent.parent / "policy" / "verifier-policy-v1.yaml"


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
    """Import aegis._verify_local and AST-extract every error_class string returned.

    Walks the module AST looking for `return (..., "AttestationXxx")` tuple returns
    (the SDK's contract is `tuple[bool, str | None]` per `_verify_local.py:191`).
    AST-based rather than regex so docstring placeholder strings (e.g., the literal
    "AttestationXxxMismatch" used as a meta-syntactic example in the verifier's
    docstring) are ignored — only strings actually returned at runtime count.

    Requires `aegis-governance[verify] >= 0.6.1` to be installed (per requirements-dev.txt).
    Uses inspect.getsource so we read the wheel's installed copy, not a stale local file.
    """
    try:
        from aegis import _verify_local  # type: ignore[import-not-found]
    except ImportError as e:
        print(
            f"ERROR: failed to import aegis._verify_local — is aegis-governance[verify] installed? ({e})",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        source = inspect.getsource(_verify_local)
    except OSError as e:
        print(f"ERROR: inspect.getsource failed: {e}", file=sys.stderr)
        sys.exit(2)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"ERROR: failed to AST-parse SDK source: {e}", file=sys.stderr)
        sys.exit(2)

    actual: set[str] = set()
    for node in ast.walk(tree):
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
            "ERROR: zero Attestation* strings found in SDK return tuples — "
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
