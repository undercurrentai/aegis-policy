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

ENFORCEMENT: `.github/workflows/tests.yml` runs this file on every PR, so the
property is gated rather than merely documented. That job was added in the same
change — before it existed, the only workflow touching `tests/` ran a single
different file and was `workflow_dispatch`-only, which made every test here
decorative.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest

# These assertions MUST run in every environment.
#
# The first version of this file used `pytest.importorskip("httpx")`, because
# gpt_review.py does `import httpx` at module scope. Verified in a clean venv:
# that made all 13 assertions SKIP while the run still reported success — a
# security guard that silently disappears is indistinguishable from one that
# passes, which is the exact failure class these tests exist to prevent.
#
# Worse, the module `sys.exit(2)`s when `openai` is missing (see its import
# block), so a bare environment would abort collection outright rather than skip.
#
# Neither dependency is reachable from the functions under test — `_safe_text`
# and `_failure_detail` are pure. So stub whatever is genuinely absent and load
# the module regardless. Real packages are preferred when present; the stub only
# fills a gap. Result: the guard cannot be silenced by an environment change.
def _ensure_module(name: str, exc_attrs: tuple[str, ...], plain_attrs: tuple[str, ...] = ()) -> None:
    if name in sys.modules:
        return  # idempotent — see the __spec__ note below
    if importlib.util.find_spec(name) is not None:
        return  # real package available — always prefer it
    stub = types.ModuleType(name)
    # types.ModuleType leaves __spec__ unset (None). CPython's find_spec checks
    # sys.modules FIRST and *raises* ValueError on a cached module with no spec,
    # so an unset __spec__ poisons every later find_spec/importorskip in the
    # session — importorskip would return this stub instead of skipping, and a
    # future capability check would silently test against a mock.
    stub.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    for attr in exc_attrs:
        setattr(stub, attr, type(attr, (Exception,), {}))
    # Non-exception names must NOT subclass Exception: `OpenAI` is a client
    # class, and making it throwable lets `raise openai.OpenAI(...)` typecheck
    # while `client.responses` raises AttributeError — which is absent from
    # gpt_review's `except (OpenAIError, httpx.HTTPError, OSError)` tuple and
    # would escape to main()'s broad net, faking a fail-closed result via
    # entirely the wrong code path.
    for attr in plain_attrs:
        setattr(stub, attr, type(attr, (), {}))
    sys.modules[name] = stub


_ensure_module("httpx", ("HTTPError",))
_ensure_module("openai", ("APIError", "OpenAIError", "RateLimitError"), ("OpenAI",))

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MODULE_PATH = _REPO_ROOT / ".github" / "scripts" / "gpt_review.py"

_spec = importlib.util.spec_from_file_location("gpt_review", _MODULE_PATH)
assert _spec and _spec.loader
gr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gr)

# Shaped like a real OpenAI key so _SECRET_PATTERNS' {16,} length floor applies.
_FAKE_KEY = "sk-proj-AbCdEf0123456789XyZwVuTsRq"
_FAKE_BEARER = "Bearer AbCdEf0123456789XyZwVuTsRq"

# THE shape the docstring actually cites — and the one the original pattern let
# through. `sk-[A-Za-z0-9_-]{16,}` cannot match it: `*` and `.` are outside the
# character class, so the match dies after 5 chars and never reaches {16,}.
# The first version of this file passed only because _FAKE_KEY above is
# UNMASKED — a shape the real auth error never has. The test proved a property
# the production data does not exhibit.
_MASKED_KEY_STARS = "sk-pr*******************dEfA"
_MASKED_KEY_DOTS = "sk-...AbCd"


class _Obj:
    """Stand-in for an SDK response object (attribute access)."""

    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)


class TestSanitizerPrimitive:
    def test_redacts_openai_key(self) -> None:
        assert _FAKE_KEY not in gr._safe_text(f"leaked {_FAKE_KEY} here")

    def test_redacts_bearer_token(self) -> None:
        assert "<redacted-secret>" in gr._safe_text(_FAKE_BEARER)

    def test_redacts_masked_openai_key_stars(self) -> None:
        """The documented threat: OpenAI's partially-masked echo in auth errors.

        Asserts the key TAIL is gone too — a sanitizer matching only the
        `sk-…` prefix leaves the revealing suffix residue and still passes an
        absence-of-whole-string check (v1.4.1 audit)."""
        out = gr._safe_text(f"Incorrect API key provided: {_MASKED_KEY_STARS}. You can find...")
        assert _MASKED_KEY_STARS not in out
        assert "<redacted-secret>" in out
        assert _MASKED_KEY_STARS[-4:] not in out, "masked-key tail residue survived"

    def test_redacts_masked_openai_key_dots(self) -> None:
        out = gr._safe_text(f"Incorrect API key provided: {_MASKED_KEY_DOTS}")
        assert _MASKED_KEY_DOTS not in out
        assert _MASKED_KEY_DOTS[-4:] not in out, "masked-key tail residue survived"

    # Bodies are deliberately the literal word EXAMPLE repeated: these must be
    # long enough to clear each pattern's length floor, but must never look like
    # a live credential to a secret scanner or to a human skimming the diff.
    @pytest.mark.parametrize(
        "secret",
        [
            "org-EXAMPLEEXAMPLEEXAMPLE",
            "proj_EXAMPLEEXAMPLEEXAMPLE",
            "uk_live_EXAMPLEEXAMPLEEXAMPLE",
            "ghs_EXAMPLEEXAMPLEEXAMPLE",
            "github_pat_EXAMPLEEXAMPLEEXAMPLE",
            "AKIAIOSFODNN7EXAMPLE",  # AWS's own documented placeholder
        ],
    )
    def test_redacts_other_credential_shapes(self, secret: str) -> None:
        """Reachable via an OpenAI error, an AEGIS 401, or a diff line the model quotes."""
        assert secret not in gr._safe_text(f"failure involving {secret} here")

    def test_redacts_url_embedded_credentials(self) -> None:
        out = gr._safe_text("cloning https://user:sup3rS3cretPassw0rd@proxy.internal:8080/x")
        assert "sup3rS3cretPassw0rd" not in out
        assert "https://" in out, "the scheme must survive — only userinfo is stripped"

    def test_preserves_non_secret_text(self) -> None:
        msg = "Your account is not active, please check your billing details"
        assert gr._safe_text(msg) == msg

    def test_preserves_ordinary_review_prose(self) -> None:
        """Over-redaction would make the reviewer useless — pin the common case."""
        msg = "In `gpt_review.py:659` the call to write_text() should use _safe_text()."
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


class TestSuccessPathIsSanitized:
    """The fallback path was guarded; the SUCCESS path — far more text — was not.

    `_write_fallback` reasons are short. The success path publishes the model's
    entire review, and SYSTEM_PROMPT directs it to cite file:line evidence from
    the diff and names "secret leak" as a CRITICAL finding class. So a PR that
    leaks a credential — exactly what this reviewer exists to catch — would get
    that credential republished by the reviewer's own public comment.

    This is a source-level guard, stated plainly: reaching the real success path
    needs a live API call. It pins the one property that matters (the write is
    routed through the sanitizer) without pretending to exercise the request.
    """

    def test_every_markdown_write_routes_through_safe_text(self) -> None:
        """AST-walked, not line-regexed: two of the three real call sites are
        already multi-line, so a single-line regex captured only the bare
        `write_text(` prefix and its `"markdown" in w` filter matched nothing
        — a reformat (or variable rename) made the guard vacuously green
        while the sanitizer could be deleted (v1.4.1 audit,
        mutation-verified). Walk the AST: EVERY args.output.write_text call's
        argument expression must route through _safe_text (or the fallback
        writer, which sanitizes internally)."""
        import ast

        src = _MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        write_calls = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "write_text"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "output"
            ):
                write_calls.append(node)
        assert write_calls, "no args.output.write_text site found — did the emit path move?"
        unsanitized = []
        for call in write_calls:
            arg_src = ast.get_source_segment(src, call.args[0]) if call.args else ""
            if "_safe_text(" not in (arg_src or "") and "_fallback" not in (arg_src or ""):
                unsanitized.append(ast.get_source_segment(src, call) or "<unparsed>")
        assert not unsanitized, (
            f"write site(s) publish unsanitized model output: {unsanitized}. "
            "gpt_review.md is posted verbatim as a PR comment on a PUBLIC repo."
        )


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
