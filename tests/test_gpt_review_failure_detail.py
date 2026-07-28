"""`gpt_review.py` must not leak a key into a PUBLIC PR comment.

WHY THIS EXISTS
---------------
`_write_fallback` writes `gpt_review.md`, which the workflow posts verbatim as a
PR comment. This repository is PUBLIC. So every string that reaches a fallback
reason is published.

The module already knew this: `_SECRET_PATTERNS` + `_safe_exc` exist precisely to
strip `sk-…` / `Bearer …` before emission, and every pre-existing
`_write_fallback` call site routes through `_safe_exc`. When the failure-reason
path started surfacing `response.error` (so an unfunded-account failure stops
looking identical to a capacity error), it initially bypassed that sanitizer —
an API-sourced string published unsanitized. OpenAI echoes a partially-masked
key in some auth errors ("Incorrect API key provided: sk-…"), so the exposure
was real, not theoretical.

These tests pin the property so it cannot silently regress.

SCOPE NOTE (honest): no CI job currently runs the full `tests/` directory — only
`e2-action-selftest.yml` runs a single file, and it is `workflow_dispatch`-only.
These therefore guard local `pytest tests/` runs and document the invariant; they
do not gate CI today. Wiring a full-suite job is tracked separately.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

# gpt_review.py imports httpx at module level. Skip rather than fail the whole
# file if the environment lacks it — several CI jobs install only pyyaml.
pytest.importorskip("httpx", reason="gpt_review.py imports httpx at module scope")

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MODULE_PATH = _REPO_ROOT / ".github" / "scripts" / "gpt_review.py"

_spec = importlib.util.spec_from_file_location("gpt_review", _MODULE_PATH)
assert _spec and _spec.loader
gr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gr)

# Shaped like a real OpenAI key so _SECRET_PATTERNS' {16,} length floor applies.
_FAKE_KEY = "sk-proj-AbCdEf0123456789XyZwVuTsRq"
_FAKE_BEARER = "Bearer AbCdEf0123456789XyZwVuTsRq"


class _Obj:
    """Stand-in for an SDK response object (attribute access)."""

    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)


class TestSanitizerPrimitive:
    def test_redacts_openai_key(self) -> None:
        assert _FAKE_KEY not in gr._safe_text(f"leaked {_FAKE_KEY} here")

    def test_redacts_bearer_token(self) -> None:
        assert "<redacted-secret>" in gr._safe_text(_FAKE_BEARER)

    def test_preserves_non_secret_text(self) -> None:
        msg = "Your account is not active, please check your billing details"
        assert gr._safe_text(msg) == msg

    def test_safe_exc_still_delegates_correctly(self) -> None:
        """_safe_exc was refactored onto _safe_text — behavior must not drift."""
        out = gr._safe_exc(ValueError(_FAKE_KEY))
        assert out.startswith("ValueError: ")
        assert _FAKE_KEY not in out


class TestFailureDetailIsSanitized:
    """THE guard: an API-sourced error must never publish a key."""

    def test_sdk_object_error_is_redacted(self) -> None:
        final = _Obj(
            status="failed",
            error=_Obj(
                code="invalid_api_key",
                message=f"Incorrect API key provided: {_FAKE_KEY}",
            ),
        )
        detail = gr._failure_detail(final)
        assert _FAKE_KEY not in detail, "API key reached a public-bound string"
        assert "invalid_api_key" in detail, "the useful part must survive"

    def test_dict_error_is_redacted(self) -> None:
        final = _Obj(status="failed", error={"code": "x", "message": _FAKE_KEY})
        assert _FAKE_KEY not in gr._failure_detail(final)

    def test_incomplete_details_is_redacted(self) -> None:
        final = _Obj(
            status="incomplete",
            error=None,
            incomplete_details={"reason": f"stopped near {_FAKE_KEY}"},
        )
        assert _FAKE_KEY not in gr._failure_detail(final)


class TestFailureDetailShapes:
    """All four response shapes the API can present."""

    def test_sdk_object(self) -> None:
        final = _Obj(status="failed", error=_Obj(code="insufficient_quota", message="no funds"))
        assert gr._failure_detail(final) == " — insufficient_quota: no funds"

    def test_dict(self) -> None:
        final = _Obj(status="failed", error={"code": "account_inactive", "message": "inactive"})
        assert gr._failure_detail(final) == " — account_inactive: inactive"

    def test_incomplete_fallback(self) -> None:
        final = _Obj(status="incomplete", error=None, incomplete_details={"reason": "max_output_tokens"})
        assert gr._failure_detail(final) == " — incomplete: max_output_tokens"

    def test_nothing_available_degrades_to_empty(self) -> None:
        """Never invent a reason — the caller then reports the bare status."""
        assert gr._failure_detail(_Obj(status="failed", error=None)) == ""


class TestFailClosedPreserved:
    """Surfacing the reason must not weaken the fail-closed posture."""

    def test_fallback_still_requests_changes_at_high(self, tmp_path: Path) -> None:
        out = tmp_path / "gpt_review.md"
        gr._write_fallback(out, "response status was 'failed', not completed — x: y")
        body = out.read_text(encoding="utf-8")
        verdict = re.search(r"(?im)^##[ ]*Verdict[^\n]*\n\s*\n\s*(\w+)", body)
        concern = re.search(r"(?im)^##[ ]*Max Concern[^\n]*\n\s*\n\s*(\w+)", body)
        assert verdict and verdict.group(1) == "REQUEST_CHANGES"
        assert concern and concern.group(1) == "HIGH"

    def test_fallback_discloses_it_did_not_review(self, tmp_path: Path) -> None:
        out = tmp_path / "gpt_review.md"
        gr._write_fallback(out, "boom")
        assert "did NOT review" in out.read_text(encoding="utf-8")
