# `aegis-verify-attestation.yml` — reusable GitHub workflow

Job-level orchestration wrapper around the composite Action shipped in Sprint 5/E2.
Consumers invoke verification via `uses:` on a JOB (not a step) and receive the
same 9 outputs back from a single `verify` job.

Sprint 5/E3 — closes cosmic-flute task #29. See also:

- `actions/verify-aegis-attestation/README.md` — composite Action docs (the STEP-level surface this workflow wraps)
- `.github/workflows/aegis-verify-attestation.yml` — the workflow source
- Cosmic-flute §35 — execution plan

---

## TL;DR

```yaml
jobs:
  verify-attestation:
    uses: undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<sha>
    with:
      envelope: "@artifacts/envelope.json"
      expected-digest: ${{ needs.build.outputs.sha256 }}
      expected-environment: production
      replay-store-path: .github/.aegis-replay.log
      aegis-sdk-git-ref: dc9c9df  # until task #59 PyPI publish
    secrets:
      AEGIS_SDK_FETCH_TOKEN: ${{ secrets.AEGIS_SDK_FETCH_TOKEN }}

  deploy:
    needs: verify-attestation
    if: needs.verify-attestation.outputs.valid == 'true'
    runs-on: ubuntu-latest
    steps:
      - run: ./scripts/deploy.sh
        env:
          AEGIS_DECISION_ID: ${{ needs.verify-attestation.outputs.decision-id }}
```

**Pin by immutable commit SHA, never `@main`** — same rationale as the composite Action (see ADR-001 §Decision).

---

## When to use composite Action vs reusable workflow

Both surfaces exist for a reason. Pick based on consumer ergonomics.

| Concern | Composite Action (E2) | Reusable workflow (E3, this file) |
|---|---|---|
| Invocation level | Step (`uses:` inside `steps:`) | Job (`uses:` inside `jobs:`) |
| Caller controls `runs-on` | YES (caller's job sets it) | NO (workflow's job sets it; `runs-on` is an input with default `blacksmith-4vcpu-ubuntu-2404`) |
| Caller orchestrates Python setup + checkout | YES (caller invokes `actions/setup-python` first) | NO (workflow handles it internally) |
| Best when | You want to splice verify into an existing job between custom build/test/deploy steps | You want verify as a separate job with `needs:` chain — simpler consumer surface |
| Industry precedent | SLSA `slsa-installer` (Go binary installer) | SLSA `generator_generic_slsa3.yml` (the canonical reusable workflow most consumers invoke) |
| Test fixture overrides | Set env on the step: `env: AEGIS_INTERNAL_FIXTURE_MODE: "1"` | Pass test-only inputs: `with: internal-fixture-mode: "1"` — workflow maps to env |

**Recommendation**: most new consumer repos should use the reusable workflow (this file). It's a smaller consumer surface — three required inputs + `needs:` chain. The composite Action is the right choice when you're already inside a job that does build + verify + deploy in a tight step sequence, or when you need control over `runs-on`.

---

## Inputs

The reusable workflow's input set is the composite Action's 8 inputs + `runs-on` + 3 test-only inputs. The 8 standard inputs flow through to the composite verbatim; the test-only inputs map to env vars per cosmic-flute §35.11 dec C.

### Standard inputs (9)

| Input | Required | Default | Description |
|---|---|---|---|
| `envelope` | YES | — | DSSE envelope JSON. Inline string OR `@path/to/file.json` (workspace-relative). |
| `expected-digest` | YES | — | SHA-256 hex (64 lowercase chars) of the subject artifact. |
| `expected-environment` | YES | — | One of: `production` \| `staging` \| `preview`. |
| `policy-version-expected` | no | `""` | Strict-equal check. Empty = read from this repo's `policy/verifier-policy-v1.yaml` (currently `2.1.0`). |
| `replay-store-path` | no | `""` | Workspace-relative path to append-only replay-detection file. Empty = no replay check; action emits `::warning::`. |
| `python-version` | no | `3.13` | Python version for `setup-python`. |
| `aegis-sdk-version` | no | `1.0.0` | PyPI version pin for `aegis-governance[verify]`. Used when `aegis-sdk-git-ref` is empty. |
| `aegis-sdk-git-ref` | no | `""` | Optional Git ref for `aegis-sdk` install. Required until task #59 (PyPI publish) ships. |
| `runs-on` | no | `blacksmith-4vcpu-ubuntu-2404` | Runner label. Override for GitHub-hosted or self-hosted pools. |

### Test-only inputs (3) — NEVER set in production

These propagate via `env:` block on the composite step inside this workflow (matching the E2 sentinel-gate pattern from Phase 3 ultrathink probe 4):

| Input | Maps to env var | Purpose |
|---|---|---|
| `internal-fixture-mode` | `AEGIS_INTERNAL_FIXTURE_MODE` | Sentinel. Set to `"1"` to enable the next two overrides. Defaults to `""` (silently ignored). |
| `internal-keys-dir-override` | `AEGIS_KEYS_DIR_OVERRIDE` | Workspace-relative override for `keys/`. Honored only when sentinel = `"1"`. |
| `internal-policy-path-override` | `AEGIS_POLICY_PATH_OVERRIDE` | Workspace-relative override for `policy/verifier-policy-v1.yaml`. Honored only when sentinel = `"1"`. |

`scripts/verify_action.py::_fixture_mode_enabled()` silently ignores the OVERRIDEs unless the sentinel matches `"1"`. Production consumers leave all three at their empty-string defaults; the test-only path is exercised exclusively by `.github/workflows/e3-workflow-selftest.yml` (and the equivalent E2 self-test for the composite Action).

---

## Secrets

| Secret | Required | Purpose |
|---|---|---|
| `AEGIS_SDK_FETCH_TOKEN` | no | PAT with read access to private `undercurrentai/aegis-governance`. Required only when `aegis-sdk-git-ref` is set AND aegis-governance is private. Ignored on the PyPI path (post task #59). |

Pass via `secrets:` block on the `uses:` call:

```yaml
jobs:
  verify-attestation:
    uses: undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<sha>
    with:
      # ... inputs ...
    secrets:
      AEGIS_SDK_FETCH_TOKEN: ${{ secrets.AEGIS_SDK_FETCH_TOKEN }}
```

Or use `secrets: inherit` to forward ALL the caller workflow's secrets (simpler but less explicit; preferred only when the caller has no other secrets you'd accidentally expose):

```yaml
jobs:
  verify-attestation:
    uses: undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<sha>
    with:
      # ... inputs ...
    secrets: inherit
```

---

## Outputs

| Output | Description |
|---|---|
| `valid` | `true` \| `false` — overall verification outcome. |
| `error-class` | Empty on success. On failure: one of the 19 AEGIS-taxonomy strings (15 verifier-layer + 4 composite-action-layer). See composite Action's README §Error classes for the full table. |
| `decision-id` | `envelope.predicate.governance.decision_id` — UUID. |
| `artifact-digest` | `envelope.predicate.governance.artifact_digest` — echoed. |
| `environment` | `envelope.predicate.governance.environment` — echoed. |
| `policy-version` | `envelope.predicate.governance.policy_version` — echoed. |
| `expires-at` | ISO 8601 UTC. |
| `nonce` | base64 (empty for `low`/`medium` risk_class). |
| `replay-checked` | `true` if `replay-store-path` was set AND the action consulted the store; `false` otherwise. |

Reference outputs from a downstream job via `needs.<verify-job-id>.outputs.<output-name>`:

```yaml
jobs:
  verify:
    uses: undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<sha>
    # ...

  deploy:
    needs: verify
    if: needs.verify.outputs.valid == 'true'
    # ...
```

---

## Permissions union pattern

The reusable workflow declares `permissions: contents: read` at its top level. Per GitHub Actions architecture, the workflow's effective permissions are the UNION of (a) what the workflow declares and (b) what the caller workflow declares for the job that invokes it.

The caller workflow MUST declare its own permissions union — the reusable workflow's `contents: read` is the MINIMUM; the caller may need more for the downstream `deploy:` job:

```yaml
permissions:
  contents: read   # for actions/checkout in caller's other jobs
  id-token: write  # if caller's deploy job uses OIDC

jobs:
  verify:
    uses: undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<sha>
    # The reusable workflow's `verify` job runs with contents: read only —
    # NOT the caller's full union. This is intentional: verify only needs
    # to checkout this public repo + run a subprocess. Caller's downstream
    # jobs use the broader union.
    with: { ... }
```

Per [GitHub Docs on reusable workflow permissions](https://docs.github.com/en/actions/sharing-automations/reusing-workflows#supported-keywords-for-jobs-that-call-a-reusable-workflow), the caller cannot ELEVATE the reusable workflow's permissions beyond what it declares — only further restrict. So the `contents: read` floor in this file is enforced at the workflow boundary, regardless of what the caller passes.

---

## Worked example: deploy gate

```yaml
name: Build, verify, deploy
on:
  workflow_dispatch:
    inputs:
      artifact-sha256:
        description: "SHA-256 hex of the artifact to deploy"
        required: true

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      envelope-path: ${{ steps.fetch.outputs.envelope-path }}
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6
      - id: fetch
        run: |
          # ... build artifact ...
          # ... fetch attestation envelope from aegis-governance /attest ...
          echo "envelope-path=artifacts/envelope.json" >> "$GITHUB_OUTPUT"

  verify-attestation:
    needs: build
    uses: undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<sha>
    with:
      envelope: "@${{ needs.build.outputs.envelope-path }}"
      expected-digest: ${{ inputs.artifact-sha256 }}
      expected-environment: production
      replay-store-path: .github/.aegis-replay.log
      aegis-sdk-git-ref: dc9c9df  # until task #59
    secrets:
      AEGIS_SDK_FETCH_TOKEN: ${{ secrets.AEGIS_SDK_FETCH_TOKEN }}

  deploy:
    needs: verify-attestation
    if: needs.verify-attestation.outputs.valid == 'true'
    runs-on: ubuntu-latest
    steps:
      - name: Halt if verify produced unexpected error class
        # Defense-in-depth: needs.X.outputs.valid='true' is the primary gate,
        # but logging the decision_id + replay-checked is useful for audit.
        env:
          DECISION_ID: ${{ needs.verify-attestation.outputs.decision-id }}
          REPLAY_CHECKED: ${{ needs.verify-attestation.outputs.replay-checked }}
        run: echo "Deploying with AEGIS decision_id=$DECISION_ID replay_checked=$REPLAY_CHECKED"

      - run: ./scripts/deploy.sh
```

---

## Worked example: risk-class downstream gate

The verifier itself does NOT check risk_class. Consumers gate downstream:

```yaml
jobs:
  verify-attestation:
    uses: undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@<sha>
    with: { envelope: "@artifacts/envelope.json", expected-digest: ${{ ... }}, expected-environment: production }
    secrets: inherit

  extract-risk-class:
    needs: verify-attestation
    if: needs.verify-attestation.outputs.valid == 'true'
    runs-on: ubuntu-latest
    outputs:
      risk-class: ${{ steps.parse.outputs.risk-class }}
    steps:
      - id: parse
        env:
          # NEVER substitute ${{ ... }} into the run: block directly.
          # Pass via env, expand via shell. (GitHub Security Lab pattern.)
          DECISION_ID: ${{ needs.verify-attestation.outputs.decision-id }}
        run: |
          # Look up envelope from your build artifact store; here we
          # assume artifacts/envelope.json was uploaded by the build job.
          PAYLOAD_B64=$(jq -r '.payload' < artifacts/envelope.json)
          RISK_CLASS=$(base64 -d <<< "$PAYLOAD_B64" | jq -r '.predicate.governance.risk_class')
          echo "risk-class=${RISK_CLASS}" >> "$GITHUB_OUTPUT"
          echo "decision_id=$DECISION_ID risk_class=$RISK_CLASS"

  deploy:
    needs: [verify-attestation, extract-risk-class]
    # Block high/critical without explicit human approval (separate manual workflow_dispatch step).
    if: needs.verify-attestation.outputs.valid == 'true' && needs.extract-risk-class.outputs.risk-class != 'high' && needs.extract-risk-class.outputs.risk-class != 'critical'
    runs-on: ubuntu-latest
    steps:
      - run: ./scripts/deploy.sh
```

For high/critical: typically gate via `environment:` (GitHub deployment environments with required reviewers) on the `deploy:` job, instead of an `if:` condition.

---

## SHA-pinning expectations

Same rules as the composite Action (see `actions/verify-aegis-attestation/README.md` §SHA-pinning expectations):

- **Pin by 40-char commit SHA**, never `@main` or `@v<tag>`.
- **Per-PR pin bumps** via reviewed PRs in consumer repos.
- **Org-Ruleset enforcement** active since Sprint 5/E1.5 Phase 7 (2026-05-12).
- **Transitive pins**: this reusable workflow internally pins `actions/checkout@de0fac2e...` (v6) for the aegis-policy checkout step. Bumping requires a PR to this repo.

When the consumer pins `aegis-policy@<sha>` on the reusable workflow `uses:` line, the workflow uses `github.event.workflow.ref` to check out aegis-policy at the SAME `<sha>` for the composite Action invocation. This ensures byte-exact consistency between the keys, policy, scripts, and the public-key fingerprints encoded in `policy/verifier-policy-v1.yaml required_keyids`. A mismatched ref would invalidate the runtime fingerprint cross-check in `scripts/verify_action.py`.

---

## Versioning

Behavior is governed by the same three knobs as the composite Action:

1. **`policy/verifier-policy-v1.yaml policy_version`** — currently `2.1.0`.
2. **`aegis-sdk` version** — `aegis-sdk-version` input (default `1.0.0`) or `aegis-sdk-git-ref`.
3. **`keys/*` fingerprints** — Sprint 5/E1.5 ceremony 2026-05-10.

The reusable workflow adds no NEW versioning surface — it's a thin orchestration wrapper around the composite. Bumping the `@<sha>` consumers pin advances all three knobs together.

---

## References

- Cosmic-flute §35 — Sprint 5/E3 execution plan (Ultraplan-approved 2026-05-14)
- Cosmic-flute §34 — Sprint 5/E2 composite Action execution plan
- ADR-001 §Decision — trust model + SHA-pinning + replay-detection responsibility
- ADR-011 (upstream) — hybrid envelope spec + verifier-statelessness
- `actions/verify-aegis-attestation/action.yml` — composite Action source
- `actions/verify-aegis-attestation/README.md` — composite Action consumer docs (includes the full 19-string error_class taxonomy)
- `.github/workflows/aegis-verify-attestation.yml` — this workflow's source
- `.github/workflows/e3-workflow-selftest.yml` — `workflow_dispatch:` self-test for this workflow
- [SLSA-framework BYOB pattern](https://slsa.dev/spec/v1.0/use-cases-build-tool-reusable-workflow) — the architectural analog (Tool Reusable Workflow wraps Tool Callback Action)
