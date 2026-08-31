# ClayBot spine — START HERE

**Status:** review-only context pack. **Not** Clay Engine. **Not** the Thursday package app.  
**Written:** 2026-08-31 ~2:30 PM PT  
**Repo:** `rroaam/clay-ops` branch `review/claybot-spine-2026-08-31`  
**Do not merge to main** until a human says so. A green check is not production or clinical approval.

This pack exists because `clayhc/clay-engine` and `claylife/clay-engine` 404 for GitHub identity `rroaam`, and the live Thursday package is a Codex CLI dirty upload (`dpl_33Jsa4c38PZADDXgW9P1UcGDyh2n`) whose SHA `fa9ae693` is **not** in `rroaam/roam-os`. ClayBot needs a Git-readable spine of verified recent work. This is that spine.

## What this is / is not

| This is | This is not |
|---|---|
| Current-state index, decisions, design-brain, sprint/hour reports | Product UI for `/review/external-package` |
| Readable by every Clay bot from Git | A fake engine, roam-os dump, or joinclay-site rewrite |
| Review branch + draft PR | Merge, prod deploy, send, spend, PHI |

**Do not** land Thursday package UI here. FORGE lands product diffs only when a writable engine exists.

## Read in this order

1. This file
2. `design-brain.md` — FRAME / STUDIO / PAPER / FORGE operating picture
3. `chatgpt/DECISION_INDEX.md` — landed vs open
4. `chatgpt/OPEN_THREADS.md` — do not average
5. `chatgpt/DESIGN_LINEAGE.md` — visual/IA lineage
6. `chatgpt/CHAT_INDEX.md` — Clay HQ Project inventory (26 chats)
7. `live-tests/2026-08-31/TEST_06_FRAME.md` — canonical Thursday package audit (may arrive in a follow-up commit)
8. `live-tests/2026-08-31/MASTER_SPRINT_REPORT.md` — 31 Aug live-fire (may arrive in a follow-up commit)
9. `live-tests/2026-08-31/HOUR_*.md` — same-day hour

## Live this week (outranks ChatGPT)

- Thursday package (ACTIVE_REVIEW): https://clay-engine-fbxmjk9uh-r0am.vercel.app/review/external-package (`dpl_33Jsa4c38PZADDXgW9P1UcGDyh2n`, `noindex`). Canonical audit: TEST_06_FRAME.md. Ignore parked alt TEST_06_PACKAGE_ALT_HUB_FIGMA.md.
- JoinClay production: https://joinclay.com (21 Aug). Remaining = scrub, not a three-asset re-lock.
- Visual law on those artifacts: Geist · ink `#121110` · bone `#FBFAF4` · canvas `#F7F4EC` · Five Elements Fuel → Heart → Brain → Body → Blood. No lime `#D9FF78`.
- Spoken 31 Aug sequence: baseline assessment → baseline review → roadmap & 90 day. Artifact care-team: Medical Lead / Health Guide / Clay Support.
- clay-ops pytest-only: https://github.com/rroaam/clay-ops/pull/2 (not this surface).

## Hard blockers (do not work around)

1. Product engine 404 for `rroaam`: `clayhc/clay-engine`, `claylife/clay-engine`, `rroaam/clay-engine`.
2. R0AM Vercel project `clay-engine` git-links **`rroaam/roam-os`** (legacy, no `/review`, no `/lab`). Live preview is CLI + `gitDirty: 1`, actor `codex`, local branch `feat/external-review-package-2026-08-28`. Do not put package UI on roam-os, clay-ops, joinclay-site, or clay-hq.
3. GitHub MCP PAT in the Grok Bot workspace is **read-only** (403 on branch create). Cloud Agent / Cursor GitHub connection is the write path.
4. ChatGPT Clay HQ is historical lineage. Project `g-p-6a673c40ffec81918700e98ca08e7598`. Do not treat `/s/` links as the Project. Pass 1: 26 chats, empty project instructions, one Devin source (text not extracted).
5. No identifiable member PHI. Skip Vibrant PDF.

## Last-mile (human only)

Merge to protected/main · production deploy/promote · production domains/env · public publishing · sending as Clay · permanent delete of canon · permission changes · final clinical/legal/health claims · spend.

## Unblock the real engine (human)

Grant `rroaam` (or a Clay bot PAT) read/write on the private product repo Vercel already knows as `clayhc/clay-engine`, **or** push the local `feat/external-review-package-2026-08-28` tree (including dirty files) to a repo this identity can write. Until then FORGE cannot land Thursday-package review code.
