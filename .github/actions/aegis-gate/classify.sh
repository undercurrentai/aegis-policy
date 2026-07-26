#!/usr/bin/env bash
# QG48-16: AEGIS transport/HTTP failure classifier.
#
# WHY THIS FILE EXISTS
# --------------------
# The gate previously collapsed every non-200 into `exit 1`:
#
#     if [ "${CURL_RC}" -ne 0 ] || [ -z "${HTTP_CODE}" ] || [ "${HTTP_CODE}" != "200" ]
#
# so HTTP 503 (AEGIS is DOWN) was indistinguishable from a governance denial.
# On 2026-06-28 the GCP billing account for undercurrent-production closed, the
# AEGIS API began returning 503, and because the org ruleset
# `aegis-enforce-required-check` requires this job's check-run with ZERO bypass
# actors, aegis-governance's main branch became unmergeable — including the PRs
# that fix the outage. AEGIS locked itself out of its own repository.
#
# The defect is a category error: "AEGIS says no" and "AEGIS did not answer" are
# different facts, and only the first is a governance verdict.
#
# Extracted as a standalone script SPECIFICALLY so it is unit-testable. Nothing
# tested the composite's bash before; this is the highest-risk shell in the org
# and it now has a closed-vocabulary total-function test sweep.
#
# CONTRACT
# --------
# Pure function. Reads CURL_RC, HTTP_CODE, CANONICAL_HOST from the environment.
# Prints exactly one word to stdout:
#
#   ok            HTTP 200. Proceed to parse. (QG48-8 malformed-body guard still applies.)
#   availability  AEGIS is DOWN. Eligible for the degraded "unavailable" verdict.
#   rejected      AEGIS is UP and refusing us (auth / quota / bad request / app error).
#                 That is a real signal about the CALLER. ALWAYS fail-closed.
#   malformed     Unclassifiable. ALWAYS fail-closed.
#
# DESIGN RULES — do not relax any of these without adding a test:
#   * 500/501 are NOT availability. The app is up and broken -> fail closed.
#   * 401/403/429/400/422/404 are NOT availability -> fail closed. This is also
#     what makes fork PRs (empty secret -> 401) fail closed rather than sliding
#     into a degraded pass.
#   * http_code "000" with rc=0 is anomalous -> malformed, NOT availability.
#     (curl prints 000, never empty, when no response is received.)
#   * CURL_RC is a strict ALLOWLIST. Never "non-zero means outage" — that would
#     turn a malformed URL or an out-of-memory curl into a governance bypass.
#   * CANONICAL_HOST gates every availability verdict. Without it,
#     `api_url: https://nonexistent.invalid` is a one-line fail-open primitive:
#     point the gate at a dead host, get "unavailable", merge.
set -euo pipefail

CURL_RC="${CURL_RC-}"
HTTP_CODE="${HTTP_CODE-}"
CANONICAL_HOST="${CANONICAL_HOST-false}"

# A non-numeric or empty rc means we could not even determine what curl did.
if ! printf '%s' "${CURL_RC}" | grep -Eq '^[0-9]+$'; then
  echo "malformed"
  exit 0
fi

# Connection-level failures that genuinely mean "the service did not answer".
# 6=couldn't resolve host, 7=failed to connect, 28=operation timeout,
# 35=SSL connect error, 52=empty reply from server.
# Deliberately EXCLUDED: 1/2/3 (unsupported protocol, failed init, malformed
# URL), 5 (couldn't resolve proxy), 22 (HTTP >=400 with -f), 26/27 (read/out of
# memory), 43 (internal error), 55/56 (send/recv error), 63 (maximum file size).
# Those indicate a broken invocation or a broken runner, not a downed AEGIS.
_is_availability_rc() {
  case "$1" in
    6 | 7 | 28 | 35 | 52) return 0 ;;
    *) return 1 ;;
  esac
}

if [ "${CURL_RC}" -eq 0 ]; then
  case "${HTTP_CODE}" in
    200)
      echo "ok"
      ;;
    502 | 503 | 504)
      # Gateway/unavailable/timeout — the canonical outage signature. Only the
      # allowlisted canonical hosts may produce this verdict.
      if [ "${CANONICAL_HOST}" = "true" ]; then
        echo "availability"
      else
        echo "rejected"
      fi
      ;;
    "" | 000)
      # rc=0 but no response code is self-contradictory. Fail closed.
      echo "malformed"
      ;;
    *)
      # Everything else — 4xx, 500, 501, 3xx — means AEGIS (or a proxy in front
      # of it) answered. That is a verdict about us, not an outage.
      echo "rejected"
      ;;
  esac
  exit 0
fi

# curl itself failed.
#
# A non-zero rc MUST be accompanied by no response code. curl emits 000 when it
# never received a response, so a non-zero rc paired with a real HTTP code is
# self-contradictory — the exact mirror of the rc=0/code=000 case above, and it
# fails closed for the same reason. Without this guard an rc=6 paired with a 403
# classifies as `availability`, which is a fail-OPEN direction: a caller (or a
# misbehaving proxy) able to produce that pairing would convert an authorization
# rejection into a degraded pass. Caught by the closed-vocabulary sweep in
# tests/test_gate_classification.py, which is precisely why that sweep exists.
case "${HTTP_CODE}" in
  "" | 000) ;;
  *)
    echo "malformed"
    exit 0
    ;;
esac

if _is_availability_rc "${CURL_RC}" && [ "${CANONICAL_HOST}" = "true" ]; then
  echo "availability"
else
  echo "malformed"
fi
