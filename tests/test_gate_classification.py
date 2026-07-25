"""Tests for the AEGIS gate transport/HTTP failure classifier (QG48-16).

WHY THIS EXISTS
---------------
The composite action previously collapsed every non-200 into ``exit 1``, so
HTTP 503 (AEGIS is DOWN) was indistinguishable from a governance denial. When
the GCP billing account closed on 2026-06-28 and the API began returning 503,
the org ruleset ``aegis-enforce-required-check`` — which requires this job's
check-run and has ZERO bypass actors — made aegis-governance's main branch
unmergeable, including the PRs that fix the outage.

``classify.sh`` is the new decision surface that separates those two facts.
Nothing tested the composite's bash before; this is the highest-risk shell in
the org, so it gets a closed-vocabulary total-function sweep rather than a
handful of examples.

The sweep is not ceremony: it caught a real fail-OPEN bug during development.
The first implementation ignored ``HTTP_CODE`` whenever ``CURL_RC != 0``, so
``rc=6`` paired with ``403`` classified as ``availability`` — converting an
authorization rejection into a degraded pass.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

CLASSIFY = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "actions"
    / "aegis-gate"
    / "classify.sh"
)

VOCABULARY = {"ok", "availability", "rejected", "malformed"}

# The ONLY (rc, http_code) pairs that may ever yield "availability", and only
# against a canonical host. Any growth here is a governance-relevant change.
AVAILABILITY_RCS = (6, 7, 28, 35, 52)
AVAILABILITY_HTTP = ("502", "503", "504")


def classify(curl_rc: str, http_code: str, canonical: str = "true") -> str:
    proc = subprocess.run(
        ["bash", str(CLASSIFY)],
        env={
            "CURL_RC": curl_rc,
            "HTTP_CODE": http_code,
            "CANONICAL_HOST": canonical,
            "PATH": "/usr/bin:/bin",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"classifier exited {proc.returncode}: {proc.stderr}"
    return proc.stdout.strip()


class TestHappyPath:
    def test_200_is_ok(self) -> None:
        assert classify("0", "200") == "ok"


class TestAvailability:
    @pytest.mark.parametrize("code", AVAILABILITY_HTTP)
    def test_gateway_codes_are_availability(self, code: str) -> None:
        assert classify("0", code) == "availability"

    @pytest.mark.parametrize("rc", AVAILABILITY_RCS)
    def test_connection_level_rcs_are_availability(self, rc: int) -> None:
        assert classify(str(rc), "000") == "availability"


class TestRejectedNotAvailability:
    """AEGIS answered. That is a signal about the CALLER, so fail closed."""

    @pytest.mark.parametrize("code", ["500", "501"])
    def test_application_error_is_not_an_outage(self, code: str) -> None:
        # The app is up and broken. Treating this as an outage would let a
        # server-side 500 wave through merges.
        assert classify("0", code) == "rejected"

    @pytest.mark.parametrize("code", ["400", "401", "403", "404", "422", "429"])
    def test_client_and_auth_codes_fail_closed(self, code: str) -> None:
        # 401/403 is the fork-PR case: an empty secret must fail closed rather
        # than sliding into a degraded pass.
        assert classify("0", code) == "rejected"


class TestNonCanonicalHostCannotForceAvailability:
    """`api_url: https://nonexistent.invalid` must not be a fail-open primitive."""

    @pytest.mark.parametrize("code", AVAILABILITY_HTTP)
    def test_gateway_codes_off_allowlist_are_rejected(self, code: str) -> None:
        assert classify("0", code, canonical="false") == "rejected"

    @pytest.mark.parametrize("rc", AVAILABILITY_RCS)
    def test_connection_rcs_off_allowlist_are_malformed(self, rc: int) -> None:
        assert classify(str(rc), "000", canonical="false") == "malformed"


class TestContradictoryInputsFailClosed:
    @pytest.mark.parametrize("code", ["", "000"])
    def test_rc_zero_without_a_response_code_is_malformed(self, code: str) -> None:
        # curl prints 000, never empty, when no response arrives — so rc=0 with
        # no code is self-contradictory.
        assert classify("0", code) == "malformed"

    @pytest.mark.parametrize("code", ["200", "403", "503"])
    def test_nonzero_rc_with_a_real_code_is_malformed(self, code: str) -> None:
        # REGRESSION GUARD. The original implementation ignored HTTP_CODE when
        # rc != 0, so rc=6 + 403 returned "availability" — a fail-OPEN.
        assert classify("6", code) == "malformed"

    @pytest.mark.parametrize("rc", ["", "x", "-1", "1.5"])
    def test_non_numeric_rc_is_malformed(self, rc: str) -> None:
        assert classify(rc, "000") == "malformed"

    @pytest.mark.parametrize("rc", [1, 2, 3, 5, 22, 26, 27, 43, 55, 56, 63])
    def test_non_allowlisted_rcs_are_not_outages(self, rc: int) -> None:
        # The anti-"non-zero means outage" guard. A malformed URL or an
        # out-of-memory curl must never read as a downed AEGIS.
        assert classify(str(rc), "000") == "malformed"


class TestTotalFunctionSweep:
    """Whitelist-shaped: availability occurs ONLY on the enumerated pairs."""

    def test_closed_vocabulary_and_exact_availability_set(self) -> None:
        codes = [
            "",
            "000",
            "200",
            "301",
            "400",
            "401",
            "403",
            "422",
            "429",
            "500",
            "501",
            "502",
            "503",
            "504",
        ]
        observed_availability = set()
        for rc in range(0, 100):
            for code in codes:
                for canonical in ("true", "false"):
                    verdict = classify(str(rc), code, canonical)
                    assert verdict in VOCABULARY, (
                        f"rc={rc} code={code} canonical={canonical} "
                        f"produced {verdict!r}, outside the closed vocabulary"
                    )
                    if verdict == "availability":
                        observed_availability.add((rc, code, canonical))

        expected = {(0, c, "true") for c in AVAILABILITY_HTTP} | {
            (rc, c, "true") for rc in AVAILABILITY_RCS for c in ("", "000")
        }
        assert observed_availability == expected, (
            "availability verdicts drifted from the allowlist; "
            f"unexpected={sorted(observed_availability - expected)} "
            f"missing={sorted(expected - observed_availability)}"
        )


class TestAntiTier2:
    """The gate substrate MUST stay exogenous to the repo it evaluates.

    An in-process fallback that evaluates governance using code from the PR
    under review was considered and REJECTED: ``src/integration/pcw_decide.py``
    *is* the PR, so a one-line diff returning PROCEED would pass its own gate,
    and ``pip install -e .`` executes PR-authored build-backend code in a job
    holding AEGIS_API_KEY and a checks:write token. This is the durable guard
    that it never gets reintroduced.
    """

    def _gate_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / ".github" / "actions" / "aegis-gate"

    @pytest.mark.parametrize(
        "forbidden", ["actions/checkout", "pip install", "PYTHONPATH", "python -m cli"]
    )
    def test_composite_never_installs_or_checks_out_caller_code(
        self, forbidden: str
    ) -> None:
        for path in self._gate_dir().iterdir():
            if path.is_file():
                assert forbidden not in path.read_text(encoding="utf-8"), (
                    f"{path.name} contains {forbidden!r} — the gate must not "
                    "execute or evaluate code from the repo under review"
                )

    def test_allowed_api_hosts_defaults_match_across_files(self) -> None:
        """The host allowlist is declared twice and must never drift.

        Raised by the Claude Opus 4.6 second-reviewer on PR #32: the default
        embeds two hostnames in BOTH the composite and the reusable workflow.
        If they diverge, the reusable workflow silently overrides the composite
        and the security property ("only canonical hosts may yield
        `availability`") is decided by whichever file the reader did not check.
        """
        import re

        root = Path(__file__).resolve().parents[1]
        pattern = re.compile(
            r"allowed_api_hosts:.*?default:\s*['\"]?([^'\"\n]+)", re.DOTALL
        )
        composite = pattern.search(
            (root / ".github" / "actions" / "aegis-gate" / "action.yml").read_text(
                encoding="utf-8"
            )
        )
        workflow = pattern.search(
            (root / ".github" / "workflows" / "aegis-enforce.yml").read_text(
                encoding="utf-8"
            )
        )
        assert composite and workflow, "allowed_api_hosts default not found in both files"
        assert composite.group(1).split() == workflow.group(1).split(), (
            "allowed_api_hosts defaults drifted:\n"
            f"  composite: {composite.group(1)!r}\n"
            f"  workflow : {workflow.group(1)!r}"
        )

    def test_reusable_workflow_checks_out_only_aegis_policy(self) -> None:
        wf = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "aegis-enforce.yml"
        ).read_text(encoding="utf-8")
        assert wf.count("actions/checkout@") == 1, (
            "aegis-enforce.yml must contain exactly ONE checkout (the "
            "aegis-policy self-checkout). A second one is how the caller's "
            "attacker-controlled source would enter the workspace."
        )
        assert "steps.resolve_callee.outputs.repository" in wf
