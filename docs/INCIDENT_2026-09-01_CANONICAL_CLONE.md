# Incident: autonomous run destroyed uncommitted work in the canonical clone

**Date:** 2026-09-01
**Severity:** data loss, unrecoverable, small volume
**Status:** contained; scheduled execution paused pending Ryan's review
**Found by:** verification sweep while completing the NORTH team-access layer

---

## What happened

An autonomous run checked out branches directly inside `~/dev/clay-engine`, Ryan's
canonical working clone, instead of using a `git worktree`. The clone's HEAD moved
from `feat/flexjet-onepager` to `review/portal-artifact-row-2026-09-01` and then to
`main`. Uncommitted files that were present at preflight were gone afterwards.

Reflog:

```
ee83dff HEAD@{0}: checkout: moving from review/portal-artifact-row-2026-09-01 to main
ee83dff HEAD@{1}: checkout: moving from feat/flexjet-onepager to review/portal-artifact-row-2026-09-01
0d3a055 HEAD@{2}: reset: moving to HEAD
```

## What was lost

At preflight (2026-08-31 16:07) the clone had 17 dirty entries. Afterwards, 3.

**Unrecoverable** — untracked, never committed to any ref, absent from every dangling
object, and no local Time Machine snapshot exists:

- `docs/worklogs/2026-08-13-auto.md` through `2026-08-28-auto.md`, roughly 11 generated
  session worklogs
- `.claude/commands/` — not committed on any of the repo's branches, so if these were
  hand-authored slash commands they are gone
- `.claude-flow/neural/`

**Recoverable from git**, though their uncommitted deltas are lost:

- `docs/PICKUP.md`
- `.swarm/memory.db`, `.swarm/memory.db-wal`
- `.claude-flow/policy/state.json`

**Not affected:** all committed history. Every branch, commit, and blob is intact.
The overnight work itself survived and is committed on its own branches, including
`review/site-improvement-lab-2026-09-01` @ `c1299e6` and
`review/portal-artifact-row-2026-09-01`.

## Why it happened

FORGE's role file said "never reset, discard, stash away, or force-push another
worker's local changes." That covered destructive git verbs but never said the
canonical clone's working tree is off limits, and never named `git worktree` as the
required alternative. A plain `git checkout` is not obviously destructive, so the
instruction did not bite. The clone had been dirty for weeks, which made the blast
radius larger than the action looked.

## Second finding, same sweep

The Site Improvement Lab run at 11:26 started `next dev --port 3048` in the same clone
and left it running. Next.js binds all interfaces by default, so
`http://192.168.1.11:3048` returned **HTTP 200** to anything on the local network,
serving unreleased review-branch work. Stopped; the port is closed.

## What was changed

**Structural, in `config/clay_shared_context.md`, compiled into all nine `SOUL.md` files:**

- *The canonical clone is read-only.* Named the forbidden verbs explicitly — `checkout`,
  `switch`, `reset`, `clean`, `stash`, `restore` — listed the safe read commands, and
  gave the `git worktree add` recipe as the required alternative. Includes why, so it
  reads as a consequence rather than a rule.
- *Network rules.* Servers bind `127.0.0.1` only, verified with `lsof`, stopped before
  the run ends. No bot opens a tunnel or publishes a port on its own.

**Both repo-touching cron prompts** carry the same two rules verbatim.

**All three cron jobs paused** — `clay-intake-drain`, `clay-daily-workday`,
`clay-site-improvement-lab`. n8n keeps classifying and writing intake packets, so no
signal is lost while paused; the queue drains when the jobs resume.

## Still open for Ryan

1. The clone is on `main`, not `feat/flexjet-onepager` where it was left. Restoring it
   is a one-line checkout, left undone deliberately: a working-tree mutation in this
   repo is exactly what caused the incident, and it should be a human's call.
   **`clay-ops validate` fails while the clone sits on `main`**, because `main` does not
   contain the pinned canon files.
2. Whether anything in `.claude/commands/` was hand-authored and worth reconstructing.
3. Whether to resume the cron jobs.

## Honest assessment

Guardrails here are instructions in a system prompt, not enforcement. They raise the
cost of the mistake; they do not make it impossible. The durable fix is that the
canonical clone should never be writable by an autonomous run at all — a dedicated
read-only clone for bots, with worktrees cut from it, would make this class of incident
structurally unavailable rather than merely forbidden. That is a change to how the
stack is laid out and is Ryan's call, so it is recorded here rather than done.
