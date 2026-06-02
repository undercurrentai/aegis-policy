// test_verify_attestation_node.mjs — F2.2 Node test harness for the
// resolve_callee step body shared by .github/workflows/aegis-verify-attestation.yml
// AND .github/workflows/aegis-enforce.yml (cosmic-flute §45.12.5.3 9-test
// enumeration: 7 per F2.2 + §37.18.16 closure + §51 tests 8-9 for the
// REUSABLE_WORKFLOW_FILENAME env-parameterized shared resolver).
//
// What this exercises that the pre-C3 regression tests in
// tests/test_workflow_invariants.py CAN'T:
//   - Runtime semantics of the primary job.workflow_* path
//   - Runtime semantics of the referenced_workflows API fallback
//   - Anchored SELF_REGEX behavior under forgery payloads
//   - Multi-match deduplication by (owner,repo,sha) tuple
//   - U9 core.warning emission on the silent .ref fallback path
//
// The pre-C3 tests only assert SYNTACTIC pinned-SHA + setOutput-emission
// patterns at the YAML level. They cannot catch a logic error that breaks
// (say) the dedupe loop or the anchored regex — those errors would only
// surface in production CI on a cross-repo workflow_call invocation.
//
// Test contract: imports resolve() from .github/scripts/resolve_callee.mjs
// (which is parity-locked byte-for-byte against the inline YAML body) and
// exercises each branch with mocked Octokit + core via simple closures.

import test from 'node:test';
import assert from 'node:assert/strict';
import { resolve } from '../.github/scripts/resolve_callee.mjs';

// === Mock helpers (single-test scoped; reset per test) ===

function makeMockCore() {
  const calls = { info: [], warning: [], setOutput: {} };
  return {
    calls,
    info(msg) { calls.info.push(msg); },
    warning(msg) { calls.warning.push(msg); },
    setOutput(name, value) { calls.setOutput[name] = value; },
  };
}

function makeMockGithub(workflowRunData) {
  const calls = { getWorkflowRun: [] };
  return {
    calls,
    rest: {
      actions: {
        async getWorkflowRun(args) {
          calls.getWorkflowRun.push(args);
          return { data: workflowRunData };
        },
      },
    },
  };
}

function makeMockContext() {
  return { repo: { owner: 'caller-org', repo: 'caller-repo' } };
}

function resetEnv() {
  delete process.env.JOB_WORKFLOW_REPOSITORY;
  delete process.env.JOB_WORKFLOW_SHA;
  delete process.env.GITHUB_RUN_ID;
  // §51: the resolver now reads the filename from REUSABLE_WORKFLOW_FILENAME
  // (parameterized so the single resolve_callee.mjs is shared across
  // aegis-verify-attestation.yml + aegis-enforce.yml). Tests 1-7 use the verify
  // fixtures, so default to that filename here; test 8 overrides to the enforce
  // consumer and test 9 deletes it to exercise the missing-env guard.
  process.env.REUSABLE_WORKFLOW_FILENAME = 'aegis-verify-attestation.yml';
}

// === 9 test cases (7 per cosmic-flute §45.12.5.3 F2.2 + tests 8-9 per §51) ===

test('1. Primary path: job.workflow_* populated → returns callee values without API call', async () => {
  resetEnv();
  process.env.JOB_WORKFLOW_REPOSITORY = 'undercurrentai/aegis-policy';
  process.env.JOB_WORKFLOW_SHA = '0123456789abcdef0123456789abcdef01234567';
  process.env.GITHUB_RUN_ID = '99999';

  const core = makeMockCore();
  const github = makeMockGithub({ referenced_workflows: [] });
  const context = makeMockContext();

  await resolve(github, context, core);

  // Primary path returns env values
  assert.equal(core.calls.setOutput.repository, 'undercurrentai/aegis-policy');
  assert.equal(core.calls.setOutput.ref, '0123456789abcdef0123456789abcdef01234567');
  assert.equal(core.calls.setOutput.resolution_path, 'job.workflow_*');
  // Primary path does NOT call the API
  assert.equal(github.calls.getWorkflowRun.length, 0);
  // No warnings on the happy primary path
  assert.equal(core.calls.warning.length, 0);
});

test('2. Fallback single-match: 1 referenced_workflows entry matches → correct tuple resolved', async () => {
  resetEnv();
  process.env.GITHUB_RUN_ID = '99999';

  const core = makeMockCore();
  const github = makeMockGithub({
    referenced_workflows: [
      {
        path: 'undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@abcdef0123456789abcdef0123456789abcdef01',
        sha: 'abcdef0123456789abcdef0123456789abcdef01',
        ref: 'refs/heads/main',
      },
    ],
  });
  const context = makeMockContext();

  await resolve(github, context, core);

  assert.equal(core.calls.setOutput.repository, 'undercurrentai/aegis-policy');
  assert.equal(core.calls.setOutput.ref, 'abcdef0123456789abcdef0123456789abcdef01');
  assert.equal(core.calls.setOutput.resolution_path, 'referenced_workflows-API');
  assert.equal(github.calls.getWorkflowRun.length, 1);
  // No warnings (sha is set)
  assert.equal(core.calls.warning.length, 0);
});

test('3. Fallback zero-match: empty referenced_workflows → throws with disambiguation', async () => {
  resetEnv();
  process.env.GITHUB_RUN_ID = '99999';

  const core = makeMockCore();
  const github = makeMockGithub({ referenced_workflows: [] });
  const context = makeMockContext();

  await assert.rejects(
    () => resolve(github, context, core),
    (err) => {
      assert.match(err.message, /No referenced_workflows entry matched aegis-verify-attestation\.yml/);
      assert.match(err.message, /Searched 0 entries/);
      return true;
    },
  );
});

test('4. Same-tuple multi-match: 2 entries with identical (owner,repo,sha) → resolves deterministically + core.info', async () => {
  resetEnv();
  process.env.GITHUB_RUN_ID = '99999';

  const core = makeMockCore();
  const sameSha = 'abcdef0123456789abcdef0123456789abcdef01';
  const entry = {
    path: `undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@${sameSha}`,
    sha: sameSha,
    ref: 'refs/heads/main',
  };
  const github = makeMockGithub({
    referenced_workflows: [entry, { ...entry }],   // 2 entries, identical tuple
  });
  const context = makeMockContext();

  await resolve(github, context, core);

  // Resolves deterministically
  assert.equal(core.calls.setOutput.repository, 'undercurrentai/aegis-policy');
  assert.equal(core.calls.setOutput.ref, sameSha);
  // core.info emitted noting the multi-match resolution
  const multiMatchInfo = core.calls.info.find((m) => m.includes('Multi-match with identical (owner,repo,sha) tuple'));
  assert.ok(multiMatchInfo, 'Expected core.info call mentioning multi-match dedupe');
});

test('5. Divergent-tuple multi-match: 2 entries with different (owner,repo,sha) → throws with candidates', async () => {
  resetEnv();
  process.env.GITHUB_RUN_ID = '99999';

  const core = makeMockCore();
  const github = makeMockGithub({
    referenced_workflows: [
      {
        path: 'undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@sha1',
        sha: 'sha1aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1',
        ref: 'refs/heads/main',
      },
      {
        path: 'undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@sha2',
        sha: 'sha2bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb2',
        ref: 'refs/heads/main',
      },
    ],
  });
  const context = makeMockContext();

  await assert.rejects(
    () => resolve(github, context, core),
    (err) => {
      assert.match(err.message, /Multiple aegis-verify-attestation\.yml referenced_workflows entries found with DIFFERENT \(owner, repo, sha\) tuples/);
      assert.match(err.message, /sha1aaaaaaaa/);
      assert.match(err.message, /sha2bbbbbbbb/);
      return true;
    },
  );
});

test('6. SELF_REGEX forgery: longer-path payload (.yml.evil/inner.yml) does NOT match anchored regex', async () => {
  resetEnv();
  process.env.GITHUB_RUN_ID = '99999';

  const core = makeMockCore();
  // Forgery probe: a malicious path that LOOKS like aegis-verify-attestation.yml
  // but is actually a longer nested path. Anchored SELF_REGEX (^...$) MUST reject it.
  // Pre-anchored substring-includes() would have erroneously matched this.
  const github = makeMockGithub({
    referenced_workflows: [
      {
        path: 'attacker/repo/.github/workflows/aegis-verify-attestation.yml.evil/inner.yml@deadbeef',
        sha: 'deadbeef0000000000000000000000000000beef',
        ref: 'refs/heads/main',
      },
    ],
  });
  const context = makeMockContext();

  // Should throw zero-match (the forgery entry is not matched by anchored regex)
  await assert.rejects(
    () => resolve(github, context, core),
    (err) => {
      assert.match(err.message, /No referenced_workflows entry matched aegis-verify-attestation\.yml/);
      // The forgery path WAS searched (it's in the "Paths:" listing) but the
      // anchored regex correctly rejected it
      assert.match(err.message, /attacker\/repo/);
      return true;
    },
  );
});

test('7. U9 empty-.sha: entry has .ref but no .sha → core.warning emitted; falls back to .ref', async () => {
  resetEnv();
  process.env.GITHUB_RUN_ID = '99999';

  const core = makeMockCore();
  const github = makeMockGithub({
    referenced_workflows: [
      {
        path: 'undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@refs/heads/main',
        sha: '',                              // U9 trigger: empty sha
        ref: 'refs/heads/main',               // .ref is present
      },
    ],
  });
  const context = makeMockContext();

  await resolve(github, context, core);

  // U9 warning emitted
  const u9Warning = core.calls.warning.find((m) => m.includes('no immutable .sha'));
  assert.ok(u9Warning, 'Expected core.warning call mentioning empty .sha fallback (U9/F1.3)');
  assert.match(u9Warning, /falling back to mutable \.ref="refs\/heads\/main"/);
  assert.match(u9Warning, /pin by commit SHA/);
  // Falls back to .ref
  assert.equal(core.calls.setOutput.ref, 'refs/heads/main');
});

// === §51 additions: REUSABLE_WORKFLOW_FILENAME env-parameterization (QG48-D8 shared resolver) ===

test('8. §51 env-parameterized filename: REUSABLE_WORKFLOW_FILENAME=aegis-enforce.yml targets the enforce consumer', async () => {
  resetEnv();
  process.env.REUSABLE_WORKFLOW_FILENAME = 'aegis-enforce.yml';   // override the verify default
  process.env.GITHUB_RUN_ID = '99999';

  const core = makeMockCore();
  // Two entries: a verify-attestation entry that MUST be IGNORED (wrong
  // filename) + the enforce entry that MUST be selected. Proves the env-driven
  // SELF_REGEX targets the correct consumer when the shared resolver runs for
  // aegis-enforce.yml.
  const github = makeMockGithub({
    referenced_workflows: [
      {
        path: 'undercurrentai/aegis-policy/.github/workflows/aegis-verify-attestation.yml@1111111111111111111111111111111111111111',
        sha: '1111111111111111111111111111111111111111',
        ref: 'refs/heads/main',
      },
      {
        path: 'undercurrentai/aegis-policy/.github/workflows/aegis-enforce.yml@2222222222222222222222222222222222222222',
        sha: '2222222222222222222222222222222222222222',
        ref: 'refs/heads/main',
      },
    ],
  });
  const context = makeMockContext();

  await resolve(github, context, core);

  // Resolves the aegis-enforce.yml entry, NOT the verify-attestation entry
  assert.equal(core.calls.setOutput.repository, 'undercurrentai/aegis-policy');
  assert.equal(core.calls.setOutput.ref, '2222222222222222222222222222222222222222');
  assert.equal(core.calls.setOutput.resolution_path, 'referenced_workflows-API');
});

test('9. §51 missing REUSABLE_WORKFLOW_FILENAME → guard throws (fallback path only)', async () => {
  resetEnv();
  delete process.env.REUSABLE_WORKFLOW_FILENAME;   // force the guard
  process.env.GITHUB_RUN_ID = '99999';

  const core = makeMockCore();
  const github = makeMockGithub({
    referenced_workflows: [
      {
        path: 'undercurrentai/aegis-policy/.github/workflows/aegis-enforce.yml@3333333333333333333333333333333333333333',
        sha: '3333333333333333333333333333333333333333',
        ref: 'refs/heads/main',
      },
    ],
  });
  const context = makeMockContext();

  await assert.rejects(
    () => resolve(github, context, core),
    (err) => {
      assert.match(err.message, /REUSABLE_WORKFLOW_FILENAME env var not set/);
      return true;
    },
  );
});
