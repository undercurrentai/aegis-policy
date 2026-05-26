// resolve_callee.mjs — standalone ESM module (cosmic-flute §45.12.5.3 F2.2).
//
// Mirrors the inline github-script body for the resolve_callee step of
// .github/workflows/aegis-verify-attestation.yml. The Node test harness
// at tests/test_verify_attestation_node.mjs imports resolve() from this
// file and exercises each branch with mocked Octokit + core (per cosmic-
// flute §45.12.5.3 7-test enumeration).
//
// PARITY INVARIANT (load-bearing constraint, enforced by the resolve-
// callee-parity CI job in aegis-verify-attestation.yml): the content
// between the parity-begin and parity-end marker lines below MUST equal
// the body of the inline `script: |` block in aegis-verify-attestation.yml
// (after PyYAML/yq dedent). Both files use the same literal marker tokens
// (which appear ONLY in the function body below, NOT in this file header,
// so the awk extraction triggers exactly once at the function-body boundary).
//
// Drift is a build failure. Edit BOTH files together OR the parity CI gate
// fails. To preserve byte-identity after PyYAML dedent of the inline body,
// the function-body content below is intentionally NOT indented (function-
// body at 0-indent, not the conventional 2-indent).
//
// Test harness mock contract (per cosmic-flute §45.12.5.3 + the 7-test
// enumeration in tests/test_verify_attestation_node.mjs):
//   - github.rest.actions.getWorkflowRun: mock to return
//     { data: { referenced_workflows: [...] } }
//   - context.repo: { owner, repo }
//   - core: capture .info, .warning, .setOutput calls via simple closures
//   - process.env.JOB_WORKFLOW_REPOSITORY + JOB_WORKFLOW_SHA: set to mocked
//     callee values (or empty string to force fallback path)
//   - process.env.GITHUB_RUN_ID: set to mock run-id string

export async function resolve(github, context, core) {
// === BEGIN_INLINE_PARITY ===
// PRIMARY path: GitHub.com cloud — job.workflow_* returns callee values.
// Read from env vars injected by step's env: block.
const jobRepo = process.env.JOB_WORKFLOW_REPOSITORY || '';
const jobSha = process.env.JOB_WORKFLOW_SHA || '';

let resolvedRepo = jobRepo;
let resolvedRef = jobSha;
let resolutionPath = 'job.workflow_*';

if (!jobRepo || !jobSha) {
  // FALLBACK: GHES (where job.workflow_* unavailable) or future
  // regression. Mirrors gh-aw PR #24974 + canonical/get-
  // workflow-version-action production pattern.
  core.info('job.workflow_repository or job.workflow_sha empty (GHES?) — falling back to referenced_workflows API');

  const callerOwner = context.repo.owner;
  const callerRepo = context.repo.repo;
  const runId = parseInt(process.env.GITHUB_RUN_ID, 10);

  if (!Number.isFinite(runId)) {
    throw new Error('GITHUB_RUN_ID invalid; cannot resolve callee via referenced_workflows API');
  }

  const run = await github.rest.actions.getWorkflowRun({
    owner: callerOwner,
    repo: callerRepo,
    run_id: runId,
  });

  const referenced = run.data.referenced_workflows || [];
  core.info(`Found ${referenced.length} referenced_workflows entries`);

  // Find the entry matching THIS reusable workflow's filename via
  // an ANCHORED regex (not substring `.includes()`) to prevent
  // longer-path forgery — e.g., a malicious nested
  // `attacker/repo/.github/workflows/aegis-verify-attestation.yml.evil/inner.yml`
  // would have matched the previous `.includes('/.github/workflows/aegis-
  // verify-attestation.yml')` substring filter. The anchored regex
  // consolidates the substring filter + downstream owner/repo
  // extraction into a single safe pass.
  // /quality-gate QG-§37.18 Phase 2 cycle 1 finding F1.1 (MEDIUM/C2;
  // defense-in-depth — referenced_workflows is server-computed so
  // forgery is theoretical, but cheap to harden).
  //
  // U1+U2 (cosmic-flute §45.12.5.3 + §37.18.16): filename literal
  // extracted to REUSABLE_WORKFLOW_FILENAME const so a future
  // workflow rename can update it in one place + the regression
  // test in tests/test_verify_attestation_node.mjs asserts parity
  // between the const + the actual workflow filename. Closes the
  // rename hazard where SELF_REGEX would silently throw on every
  // invocation if someone renamed the file but missed this regex.
  //
  // Path format (per GitHub REST API):
  //   <owner>/<repo>/.github/workflows/<file>.yml@<ref>
  // The optional `@<ref>` suffix appears for cross-repo references.
  const REUSABLE_WORKFLOW_FILENAME = 'aegis-verify-attestation.yml';
  const SELF_REGEX = new RegExp(
    `^([^/]+)/([^/]+)/\\.github/workflows/${REUSABLE_WORKFLOW_FILENAME.replace(/\./g, '\\.')}(?:@.*)?$`,
  );
  // Collect ALL matches (not just first) to detect multi-match
  // ambiguity per /quality-gate Phase 3 /ultrathink U6 (MEDIUM/C2):
  // GitHub API does not guarantee referenced_workflows[] ordering.
  // If two entries point at the same path with different SHAs
  // (rare but possible in nested workflow_call chains where the
  // same reusable workflow is invoked at multiple SHAs), picking
  // the FIRST returned would be non-deterministic. Throw with full
  // disambiguation context so the caller can pin explicitly.
  const matches = [];
  for (const wf of referenced) {
    const m = wf.path.match(SELF_REGEX);
    if (m) {
      matches.push({ entry: wf, owner: m[1], repo: m[2] });
    }
  }
  if (matches.length === 0) {
    throw new Error(
      `No referenced_workflows entry matched ${REUSABLE_WORKFLOW_FILENAME} (anchored regex). ` +
      `Searched ${referenced.length} entries. Paths: ` +
      JSON.stringify(referenced.map((w) => w.path)),
    );
  }
  if (matches.length > 1) {
    // Allow multi-match ONLY if all entries point at the same
    // (owner, repo, sha) — that's a benign duplicate. Otherwise
    // throw with disambiguation context.
    const dedupeKey = (mm) => `${mm.owner}/${mm.repo}@${mm.entry.sha || mm.entry.ref}`;
    const uniqueKeys = [...new Set(matches.map(dedupeKey))];
    if (uniqueKeys.length > 1) {
      throw new Error(
        `Multiple ${REUSABLE_WORKFLOW_FILENAME} referenced_workflows entries found with DIFFERENT (owner, repo, sha) tuples — cannot deterministically resolve callee. ` +
        `GitHub API does not guarantee referenced_workflows[] ordering, so picking the first would be non-deterministic. ` +
        `Distinct callee tuples: ${JSON.stringify(uniqueKeys)}. ` +
        `Resolution: pin caller-side, or file aegis-policy issue with the caller's workflow context.`,
      );
    }
    core.info(`Multi-match with identical (owner,repo,sha) tuple (${uniqueKeys[0]}); resolving deterministically.`);
  }
  const matchingEntry = matches[0].entry;
  const matchedOwner = matches[0].owner;
  const matchedRepo = matches[0].repo;

  resolvedRepo = `${matchedOwner}/${matchedRepo}`;
  // Prefer immutable SHA over mutable ref (gh-aw #24974 — resists
  // branch drift during long-running jobs).
  //
  // U9/F1.3 (cosmic-flute §45.12.5.3 + §37.18.16): when .sha is
  // empty AND .ref is present, the silent fallback proceeds with
  // a mutable ref. Emit a core.warning so operators can request
  // the caller pin by commit SHA. Closes the "silent .ref fallback"
  // observability gap.
  if (!matchingEntry.sha) {
    core.warning(
      `referenced_workflows entry has no immutable .sha; falling back to mutable .ref="${matchingEntry.ref}". ` +
      `Caller may have pinned this reusable workflow by branch/tag rather than commit SHA — ` +
      `request the caller pin by commit SHA per cosmic-flute §35.5 best practice.`,
    );
  }
  resolvedRef = matchingEntry.sha || matchingEntry.ref;
  resolutionPath = 'referenced_workflows-API';
}

core.info(`Resolved callee via ${resolutionPath}: ${resolvedRepo}@${resolvedRef}`);
core.setOutput('repository', resolvedRepo);
core.setOutput('ref', resolvedRef);
core.setOutput('resolution_path', resolutionPath);
// === END_INLINE_PARITY ===
}
