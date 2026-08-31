# Canonical Repo Access Gap

## Status: CONFIRMED (scoped — see below)

`CONFIRMED` applies only to the FORGE worker on this Mac mini, under the `rroaam` GitHub
identity, verified 2026-08-31 by direct `git`/`gh` inspection of the local clone at
`~/dev/clay-engine`. The Grok/Cursor identity gap described below as `MISSING_ACCESS`
has **not** been independently retested here and should be treated as still open until
that identity is checked directly.

## What was verified (this machine, `rroaam` identity, 2026-08-31)

- **Repository owner/name:** `claylife/clay-engine`, confirmed via `gh repo view
  claylife/clay-engine --json nameWithOwner,defaultBranchRef,visibility,isPrivate` →
  `{"defaultBranchRef":{"name":"main"},"isPrivate":true,"nameWithOwner":"claylife/clay-engine","visibility":"PRIVATE"}`.
  `gh auth status` shows the active account is `rroaam` with `repo` scope.
- **Default branch:** `main` (confirmed by both `gh repo view` and
  `git symbolic-ref refs/remotes/origin/HEAD` → `refs/remotes/origin/main`).
- **Current HEAD SHA of `origin/main`:** `ee83dff179d1b42b32926d292de7397caf6dba9f`
  (commit dated 2026-07-02, "Add chief pass email formatter"). Note this is materially
  older than the four review-branch commits below — `main` has not been fast-forwarded
  to include that recent work; those commits live only on their feature/review branches.
- **Existence of the four recorded branches/commits** — all four resolve as real commits
  on `origin`; three are the current tip of their branch, one has been superseded by a
  later commit on the same branch:
  - `feat/artifact-morning-review-2026-08-26` @ `f186c91e93c4223e399d1b081ed693ae3feb390b`
    — EXISTS. The branch has since moved forward past this commit; the current tip of
    `origin/feat/artifact-morning-review-2026-08-26` is `29164bfe0d39ff96159682855b742f833ec0da52`
    (2026-08-27, "fix(artifacts): simplify markers and dividers"). The recorded commit
    `f186c91e` still exists and is an ancestor of the current branch tip.
  - `review/day-one-intake-rev5-2026-08-26` @ `ee18036a39749798289b42e807662ffc08a3b481`
    — EXISTS and is the current branch tip.
  - `review/instrument-brand-delta-2026-08-26` @ `7a55e220b818ee161bbb5455751b02df01ca086c`
    — EXISTS and is the current branch tip.
  - `review/instrument-team-media-alt-2026-08-18` @ `696f552f3352f616fd08a263dd8841c08f925256`
    — EXISTS and is the current branch tip.
  - `origin/main` is an ancestor of all four branches (confirmed via
    `git merge-base --is-ancestor origin/main origin/<branch>` for each).
- **`DESIGN.md`:** present at the root of `origin/main` HEAD.
- **`docs/DESIGN_AUTHORITY.md`:** **not present on `origin/main`.** It exists on ~28
  other branches (including all four recorded review/feat branches above, e.g.
  `feat/artifact-morning-review-2026-08-26`, `review/day-one-intake-rev5-2026-08-26`,
  `review/instrument-brand-delta-2026-08-26`, `review/instrument-team-media-alt-2026-08-18`,
  plus several `design/*` and `feat/*` branches through 2026-08-31). Anything reading
  `docs/DESIGN_AUTHORITY.md` should pin to one of those branches explicitly rather than
  assume it is reachable from `main`.

## What this does NOT resolve

- The `clay-ops` canon registry (`config/canon-registry.json`) points at a sibling path
  `../clayhc-clay-engine` for its pinned canon references (`brand-design-law`,
  `copy-language-law`, `banned-phrases-law`, `healthcare-context-insufficient`). That
  path does not exist on this machine — the actual clone lives at `~/dev/clay-engine`,
  a different name and location. This is a separate, pre-existing local-path
  misconfiguration, not a GitHub access problem, and it is why `clay-ops validate` and
  6 tests in `tests/test_copy_review.py` plus
  `tests/test_boundaries.py::test_all_canon_references_are_pinned_readonly_and_resolvable`
  still fail (`CANON_UNRESOLVABLE: Canonical repository is unavailable.`). Left
  unfixed here — out of scope for an access-verification pass and needs a decision on
  whether to symlink, relocate the clone, or repoint the registry.
- Whether the Grok/Cursor automation identity's 404 against `claylife/clay-engine` is
  fixed. Not retested in this pass. Treat `MISSING_ACCESS` as still the status for that
  identity until someone checks it directly.
- `~/dev/clay-engine`'s working tree was not touched, committed, or pushed as part of
  this verification (it currently has an unrelated dirty working tree on
  `feat/flexjet-onepager` belonging to other in-progress work, left untouched).

## What ClayBot/FORGE should do now

1. On this machine, under `rroaam`, direct reads of `~/dev/clay-engine` for exact
   current source are no longer blocked — use them instead of reconstructing from
   summaries or receipts.
2. Still do not assume the Grok/Cursor identity is unblocked — that gap is unverified,
   not fixed.
3. When reading `docs/DESIGN_AUTHORITY.md`, pin to the specific branch it's needed from;
   do not expect it on `main`.
4. The `clay-ops` canon-registry path mismatch is a separate open item — flag it for a
   human decision rather than silently reworking `config/canon-registry.json`.

## Proper fix (Grok/Cursor identity — still open)

Grant the dedicated Clay GitHub identity access to the private `claylife/clay-engine`
repository, ideally through the official GitHub app/OAuth installation with repository
access scoped to the Clay repos it needs, then have that identity re-run the same
verification independently.
