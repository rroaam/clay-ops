# TEST 07 — FORGE isolated review-branch fix

**Date:** 2026-08-31 ~2:00 PM PT  
**Agent:** FORGE  
**GitHub identity:** `rroaam`  
**Status:** shipped as draft PR. Not merged. Production impact: none.

---

## Product-repo blocker (verified live)

GitHub is connected as `rroaam`. Product engine repos remain unreachable:

| Repo | Result (live 2026-08-31) |
| --- | --- |
| `clayhc/clay-engine` | 404 |
| `claylife/clay-engine` | 404 |

No clone was made on this computer. Current product UI work is Vercel-only (R0AM `clay-engine` previews). FORGE did not attempt to invent `clayhc/clay-engine` access.

NORTH / FRAME briefs were not on disk when this task started (`TEST_01_NORTH.md`, `TEST_06_FRAME.md` absent). No named issue lived in a reachable repo.

**Reachable repos inspected:** `rroaam/clay-ops`, `rroaam/clay-hq`, `rroaam/joinclay-site`. None had open GitHub issues. Each already has a stale 2026-07-31 governance draft PR #1 (README banner only). `joinclay-site` is LEGACY (Clay v1). `clay-hq` is internal operator UI.

**Next-best reachable fix:** `rroaam/clay-ops` — existing pytest suite, no CI. Left stale governance PR #1 untouched.

---

## Shipped

| Field | Value |
| --- | --- |
| Repo | [`rroaam/clay-ops`](https://github.com/rroaam/clay-ops) |
| Base | `main` @ `c5d051006c350ebd2c478936b34994611bd2c594` |
| Review branch | `review/ci-pytest-2026-08-31` |
| HEAD SHA | `91961a05eb462e4c1d1301e3b2923e06fd905794` |
| Draft PR | https://github.com/rroaam/clay-ops/pull/2 (draft, open, not merged) |
| Preview URL | none — Python local ops repo, not a Vercel app |
| Surface / profile | Clay Ops local control plane (not member-facing; not JoinClay web/portal) |
| Cloud agent | https://cursor.com/agents/bc-77f95947-517e-47b6-99d9-18b01b441793 |
| Production impact | **none** |

### Files changed (+31 / −0, 2 files)

1. `.github/workflows/test.yml` (new) — `pull_request` → `main` and `push` → this review branch; Python 3.11 via `astral-sh/setup-uv@v6`; `uv sync --extra test` then `uv run pytest`; `contents: read` only; no secrets; no deploy.
2. `README.md` — one line under Local use: `uv run pytest`.

Application code, schemas, policies, runtime, credentials, GitHub settings, branch protection, and governance PR #1 were not modified.

---

## Evidence

**Local (cloud agent VM) and GitHub Actions, same result:** `uv sync --extra test && uv run pytest` → **143 passed, 7 failed**.

Cheap CLI:

- `uv run clay-ops doctor` — **pass**
- `uv run clay-ops validate` — **fail** (`CANON_UNRESOLVABLE`)

CI jobs (both failed with the same 7 tests):

- https://github.com/rroaam/clay-ops/actions/runs/33438928281 (push)
- https://github.com/rroaam/clay-ops/actions/runs/33438943004 (pull_request)

Failed tests (pre-existing checkout gap, not a regression from this PR):

- `tests/test_boundaries.py::test_all_canon_references_are_pinned_readonly_and_resolvable`
- six `tests/test_copy_review.py` cases

Cause: `config/canon-registry.json` pins sibling `../clayhc-clay-engine`. That checkout is not present on the review VM or GitHub Actions. Product-org engine repos 404 from `rroaam`, so the sibling cannot be fetched. Failures raise `CANON_UNRESOLVABLE`. No silent skip was added.

Screenshot matrix: N/A (no UI surface).

---

## Last-mile / what was not done

- No merge to `main`
- No production deploy / promote / domain / env change
- No permission changes
- No clone onto this computer
- No PHI ingested
- Stale governance draft https://github.com/rroaam/clay-ops/pull/1 left as-is

---

## Open decisions (human)

1. Grant `rroaam` (or a Clay bot PAT) read access to `clayhc/clay-engine` so clay-ops canon tests and `validate` can resolve. Until then, CI on this suite cannot go green.
2. Merge vs hold draft PR #2. A passing build here would prove CI wiring; current red is truthful proof the suite depends on a product repo this identity cannot see.
3. Whether to later add a documented, non-silent CI fixture for missing-canon (not done here — that would hide the access gap).

---

## Deviations

None on scope. NORTH/FRAME did not name a reachable issue; product engine 404 forced the clay-ops CI fallback. Existing governance PR #1 was not completed or replaced.
