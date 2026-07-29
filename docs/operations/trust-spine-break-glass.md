# Trust-spine break-glass (the §34.17.2 sole-keyholder cycle)

**Status:** interim procedure · **First written down:** 2026-07-28 · **Owner:** @ThermoclineLeviathan

How to merge a trust-spine change in this repository when no code owner can approve it.
A **time-boxed** procedure with a hard restore step — never a standing configuration.

> **This documents existing practice; it does not introduce it.** The pattern is referenced
> throughout `docs/ROADMAP.md` as the "cosmic-flute §34.17.2 sole-keyholder bypass cycle" and has
> run **at least 29 times** (see the Sprint 7 / G1 §48 row, which records the 29th, and the §38
> row noting `bypass_actors=[]` preserved across nine cumulative cycles). Until now the steps
> lived in transcripts and PR descriptions rather than in the repo.
>
> Writing it down is the point: a procedure this load-bearing, executed this often, against
> controls that guard **signing-key integrity**, should not depend on remembering which of two
> similarly-named rulesets has the property lever, or on rediscovering the 422 each time.

---

## Why this exists

Three individually-reasonable controls compose into a state where the only code owner cannot
merge a trust-spine change:

1. **`.github/CODEOWNERS`** assigns the trust-spine paths — `.github/`, `keys/`, `schema/`,
   `policy/`, `scripts/`, `actions/`, `docs/architecture/` — solely to `@ThermoclineLeviathan`.
2. **All three org rulesets** set `require_code_owner_review: true` with
   `required_approving_review_count: 1`.
3. **`aegis-attestation-required-checks`** (org ruleset `16294975`, scoped to this repo by
   `repository_name`) has **`bypass_actors: []`** — nobody, including org admins.

GitHub forbids self-approval, and the `@aegis-auto-reviewer` aggregator is **designed** never to
auto-approve a trust-spine change (`.github/workflows/ai-second-review.yml`, and the
`trust_spine_globs` list in `.aegis-trust-spine-paths.yaml`). So an author who is also the sole
code owner has no in-band path to merge.

This is the same structural shape as the 2026-06/07 outage, where a required check depended on the
service it governed. Here, the approval requirement depends on a reviewer who cannot exist.

**The real fix is a second human or team code owner** — tracked in `docs/ROADMAP.md`. Until that
exists, this procedure is the honest interim: explicit, auditable, and reverted immediately.

---

## Before you start

Ask whether the change actually needs this. It does **not** if:

- The change touches only non-trust-spine paths (`docs/` outside `architecture/`, `tests/`,
  `README.md`). `*` in CODEOWNERS lists both `@ThermoclineLeviathan` **and**
  `@aegis-auto-reviewer`, so the aggregator can approve those normally.
- A second reviewer is available. Ask them. This procedure is for when nobody can.

If a genuine second reviewer exists, use them — every use of this procedure is a small erosion.

---

## Procedure

### 1. Snapshot the ruleset first

Non-negotiable. The restore in step 5 is a diff against this file, so without it you are restoring
from memory.

```sh
gh api orgs/undercurrentai/rulesets/16294975 > /tmp/ruleset-16294975-before.json
python3 -c "
import json; d=json.load(open('/tmp/ruleset-16294975-before.json'))
print('bypass_actors:', d.get('bypass_actors'))
print('enforcement :', d['enforcement'])
print('rules       :', sorted({r['type'] for r in d['rules']}))
"
```

Expect `bypass_actors: []`. If it is already non-empty, **stop** — someone left a bypass in place
and that is the thing to investigate.

### 2. Add the bypass with a FULL payload

A partial `PUT` fails:

```
422 Validation Failed
Rule configurations contain invalid rule with type pull_request:
Parameters is invalid for this rule type: Unexpected parameter `allowed_dismissal_actors`
```

GitHub injects `allowed_dismissal_actors` when merging a partial payload, then rejects the field
its own update endpoint does not accept. Send the whole object, rebuilt from the snapshot.

**The 422 is protective** — it rejects atomically and leaves the ruleset untouched. If you see it,
nothing has changed yet.

```sh
python3 -c "
import json, copy
d = json.load(open('/tmp/ruleset-16294975-before.json'))
json.dump({
    'name': d['name'], 'target': d.get('target','branch'),
    'enforcement': d['enforcement'], 'conditions': d['conditions'],
    'rules': copy.deepcopy(d['rules']),
    'bypass_actors': [{'actor_id': 1, 'actor_type': 'OrganizationAdmin', 'bypass_mode': 'always'}],
}, open('/tmp/ruleset-payload.json','w'))
"
gh api orgs/undercurrentai/rulesets/16294975 --method PUT --input /tmp/ruleset-payload.json > /tmp/ruleset-after.json
```

### 3. Verify ONLY `bypass_actors` changed

Do this before merging. If anything else moved, restore immediately and start over.

```sh
python3 -c "
import json
b = json.load(open('/tmp/ruleset-16294975-before.json'))
a = json.load(open('/tmp/ruleset-after.json'))
for k in ('name','target','enforcement','conditions','rules'):
    same = json.dumps(a.get(k), sort_keys=True) == json.dumps(b.get(k), sort_keys=True)
    print(f'{k:12} {\"unchanged\" if same else \"*** CHANGED ***\"}')
checks = [c['context'] for r in a['rules'] if r['type']=='required_status_checks'
          for c in r['parameters']['required_status_checks']]
print('required checks:', len(checks), '(expect 7 as of 2026-07-29)')
print('code_owner_review:', [r['parameters'].get('require_code_owner_review')
      for r in a['rules'] if r['type']=='pull_request'])
"
```

Every required check must survive — 7 as of 2026-07-29 (`Test suite (py3.12)` + `Test suite
(py3.13)` joined the original five). The count moves whenever the required-check set changes, so
trust the snapshot diff over a remembered number: what matters is that the `rules` field compares
**unchanged** against your step-1 snapshot, and that `require_code_owner_review` is still `true`.
You are suspending *who may bypass*, not *what is required*.

### 4. Merge

```sh
gh pr merge <N> --squash --admin --delete-branch
gh pr view <N> --json state --jq .state   # must print MERGED
```

`gh` can exit 0 without merging when a rule still blocks — check the state, do not trust the exit
code.

### 5. Restore immediately, and verify byte-identical

Run this in the **same working session** as step 4. Do not defer it.

```sh
python3 -c "
import json, copy
d = json.load(open('/tmp/ruleset-16294975-before.json'))
json.dump({
    'name': d['name'], 'target': d.get('target','branch'),
    'enforcement': d['enforcement'], 'conditions': d['conditions'],
    'rules': copy.deepcopy(d['rules']), 'bypass_actors': [],
}, open('/tmp/ruleset-restore.json','w'))
"
gh api orgs/undercurrentai/rulesets/16294975 --method PUT --input /tmp/ruleset-restore.json > /dev/null

python3 -c "
import json, subprocess
b = json.load(open('/tmp/ruleset-16294975-before.json'))
a = json.loads(subprocess.run(['gh','api','orgs/undercurrentai/rulesets/16294975'],
                              capture_output=True, text=True).stdout)
diff = [k for k in ('name','target','enforcement','conditions','rules','bypass_actors')
        if json.dumps(a.get(k), sort_keys=True) != json.dumps(b.get(k), sort_keys=True)]
print('differing fields:', diff or 'NONE — byte-identical to the pre-change snapshot')
"
```

`NONE` is the only acceptable result.

---

## Rules

- **Never leave a standing bypass on `16294975`.** It also guards
  `keys/ ↔ required_keyids SHA-256 parity` and `SDK ↔ policy error_class parity` — signing-key
  and error-contract integrity. A permanent bypass there trades a durable security property for a
  one-time convenience.
- **Minutes, not hours.** Add → merge → restore, in one sitting.
- **The `aegis-enforce-mode` property lever does NOT apply here.** That scopes
  `aegis-enforce-required-check` (`17101026`) by `repository_property`, so setting the property
  outside `[shadow, enforce]` drops the repo from *that* ruleset. `16294975` scopes by
  `repository_name` — different rule, no lever. Do not reach for it and conclude it is broken.
- **Read rulesets org-scoped, not repo-scoped.** `repos/{owner}/{repo}/rulesets/{id}` **truncates
  `conditions`**: it returned only `ref_name` and omitted the `repository_property` block
  entirely, which nearly led to the conclusion that a designed break-glass lever did not exist.
  Always use `orgs/{org}/rulesets/{id}`.
- **Every use is auditable.** GitHub logs ruleset changes in the org audit log, and the
  add/remove pair is visible there. Do not treat this as a quiet workaround.

---

## Precedent

The cycle predates this document by roughly two months and dozens of executions. `docs/ROADMAP.md`
records it from Sprint 5 / E2 (PR #5, 2026-05-13) onward — "squash-merged via admin per cosmic-flute
§34.17.2 sole-keyholder pattern; `bypass_actors=[]` restored post-merge" — through the 29th
cumulative cycle at §48 (2026-05-31).

Most recent: **2026-07-25**, to land `aegis-policy#32` (the availability-vs-verdict gate fix),
which touched `.github/actions/aegis-gate/` and `.github/workflows/aegis-enforce.yml`. The PR was
unapprovable by its author and green on the three required checks that reported — the two parity
checks never ran, because #32's file set matched neither workflow's then-active `paths:` filter.
(An earlier revision of this paragraph said "green on all five required checks"; that was written
from memory and is wrong. The never-reporting-required-check wedge it exemplifies was diagnosed
and fixed on 2026-07-29 — the parity workflows now run on every PR.) Restore verified
byte-identical to the pre-change snapshot.

That instance is worth keeping in view, because it is the argument for the real fix: **the change
being blocked was itself the fix for a governance control that had locked a repository.** A
procedure that has run 29+ times is not an exception any more — it is the de facto merge path for
trust-spine work, and it should be replaced by a second reviewer rather than refined further.
