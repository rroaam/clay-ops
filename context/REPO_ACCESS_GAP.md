# Canonical Repo Access Gap

## What is confirmed

Recent Clay review receipts in Drive identify the implementation repository as:

`claylife/clay-engine`

Recent branches/commits recorded there include:

- `feat/artifact-morning-review-2026-08-26` @ `f186c91e93c4223e399d1b081ed693ae3feb390b`
- `review/day-one-intake-rev5-2026-08-26` @ `ee18036a39749798289b42e807662ffc08a3b481`
- `review/instrument-brand-delta-2026-08-26` @ `7a55e220b818ee161bbb5455751b02df01ca086c`
- design guide source branch `review/instrument-team-media-alt-2026-08-18` @ `696f552f3352f616fd08a263dd8841c08f925256`

These receipts strongly indicate the recent work is already Git-backed.

## What is failing

The GitHub identity currently available to the Grok/Cursor automation cannot resolve `claylife/clay-engine` and gets 404. It can access `rroaam/clay-ops`.

This should be treated as an authentication/repository-membership problem.

## What ClayBot/FORGE should do

Until access is restored:

1. Do not claim the recent work is absent from Git.
2. Do not recreate Clay Engine UI inside `rroaam/clay-ops`.
3. Use the review receipts/previews to understand current state.
4. Keep code implementation blocked when exact current source code is required.
5. Continue non-code work: product reconciliation, design critique, copy review, source indexing, QA against live previews, and review packaging.

## Proper fix

Grant the dedicated Clay GitHub identity access to the private `claylife/clay-engine` repository, ideally through the official GitHub app/OAuth installation with repository access scoped to the Clay repos it needs.

Once fixed, FORGE should immediately verify:

- repository owner/name
- default branch
- current HEAD SHA
- existence of the recorded branches/commits above
- latest active branches/PRs since 2026-08-26
- current `docs/DESIGN_AUTHORITY.md`, `DESIGN.md`, Clay Brain language files, and current implementation code

Then update this file from `MISSING_ACCESS` to `CONFIRMED` and refresh the rest of the context pack from the live repo.
