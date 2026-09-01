# TEST 05 — Unified review queue
**Written:** 2026-08-31 ~2:05 PM PT; patched ~2:15 PM PT — Monday Creative Sprint closeout added as dated READY, not today’s shipping surface  
**Owner:** NORTH  
**Rule:** Live links + status. Mark **UNVERIFIED** if not reverified this run. Review ≠ production. No PHI.

## Production (do not confuse with review)
| Surface | URL / id | Status this run | Notes |
|---|---|---|---|
| **joinclay.com** | https://joinclay.com | **PRODUCTION since 21 Aug** (Rajiv `#clay-studios`) | Instrument landing is the homepage. Funnel untouched. Live ≠ locked (Deven 25 Aug scrub + phone-number still open). |
| clay-engine production (R0AM) | `clay-engine.vercel.app` / `clay-engine-r0am.vercel.app`; `dpl_41k7ViZP64VwS6rWKTfuErgzsdKR` | **READY** 16 Jun 2026 | Commit `roam/launch-build-jun16`. Not this week’s review work. |
| 27 Aug R0AM CLI fail | project `clay-staff-member-record-2026-08-27-1787858155573-3MCG` | **CLOSED** — project 404 | One-off `--prod` CLI. Email `1a044a724100bfd1` still unread. **Not an open prod incident.** Note: `context/vercel-27aug-fail.md`. |
| Monday Creative Sprint closeout (same host HQ `/`) | https://clay-monday-review-closeout-2026-08.vercel.app/review/monday-creative-sprint · https://clay-monday-review-closeout-2026-08.vercel.app/ | **READY closeout, dated ~4–13 Aug** | T1 for that sprint era only. **Not today’s shipping surface.** Not clay-engine. `get_deployment` on team `r0am` 404s this hostname (one-off alias). Ingest: `context/monday-creative-sprint.md`. Prefer 31 Aug Slack + `fbxmjk9uh` package + joinclay.com when they disagree. |

## Live review previews (use these)
HTTP 200 this run unless noted. `x-robots-tag: noindex`. Synthetic / not member-final.

| Surface | Link | Deploy | HTTP | What it is | Awaiting |
|---|---|---|---|---|---|
| **Team review package (canonical)** | https://clay-engine-fbxmjk9uh-r0am.vercel.app/review/external-package | `dpl_33Jsa4c38PZADDXgW9P1UcGDyh2n` READY, 28 Aug 14:31 PT, `feat/external-review-package-2026-08-28` | 200 | Ryan posted 31 Aug 11:41 PT. Field Record + Roadmap + 90-Day. Title `Clay Connected Review Package`. | Remaining edits; human team send |
| Field Record | https://clay-engine-6m1k1mkmq-r0am.vercel.app/ops/member-record | `dpl_2pQg5pnzHGtaA8iLncHcLDPRjWVy` | 200 | Title `Clay Field Record \| Internal Review`. Fixture only. | Portal unification (prototypes) |
| Uploads hub (newer same lane) | https://clay-engine-iu0zuxn73-r0am.vercel.app | 28 Aug 13:15 PT | **listed READY; path not separately fetched this write** | `fix(ops): polish upload hub navigation` | Prefer over 6m1k1mkmq for uploads QA |
| Roadmap guided | https://clay-engine-geubcggc7-r0am.vercel.app/lab/artifact-styling-lab/roadmap-review?fixture=full&experience=guided | `dpl_7Xr2Xp5tP59en3MwBonBRZF7ACP5` | 200 | `filled-mock`. Also linked from package host. | Remaining Roadmap edits |
| 90-Day on package host | https://clay-engine-fbxmjk9uh-r0am.vercel.app/lab/artifact-styling-lab/90-day-plan?state=filled-mock&experience=guided | same `dpl_33Jsa4c38PZADDXgW9P1UcGDyh2n` | **path from package HTML; host 200** | Thursday 90-Day. Canonical send is still the package. | Prescriptiveness decision |
| Later guided 90-Day (same feat branch) | https://clay-engine-d8lz8o4kc-r0am.vercel.app | `dpl_5fr7VHSh1gtBx9LPKPW8t52UJsvY` READY, 28 Aug 12:00 PT | **listed READY** | `fix(artifacts): restore guided plan sections`. Later than `geubcggc7`; earlier than package `fbxmjk9uh`. | QA restored Movement/Protocols/Sleep vs six-slide cut |
| Five Elements radar (optional) | https://clay-engine-j98kzo49m-r0am.vercel.app | 27 Aug 19:26 PT | **listed READY** | Radar IP. Not the Thursday package. | Optional |
| Day One Intake Rev 5 | https://clay-engine-pyve0t08w-r0am.vercel.app/day-one | `dpl_4kSmrNe6LHGpfsrhiHYA916td2ZB` | 200 | Title `Clay · Day One Intake Rev 5 (review)`. Current language is **Intake**. | Thursday Intake pass |
| Artifact styling lab | https://clay-engine-au2oam8m8-r0am.vercel.app/lab/artifact-styling-lab | `dpl_ANkb18ix3ixxqRQ9cJCXbPk9Etfs` | 200 | Nine templates. | Gallery only |
| Landing v4 Instrument (lab) | https://clay-engine-pf42yr1vk-r0am.vercel.app/lab/landing-v4-directions/instrument | `dpl_8rkCdKoKGUpckLVAMCzdcw81zCZp` | 200 | Lab exploration. **Production is joinclay.com, not this.** | Remaining production scrub, not a cutover |

## Superseded (do not send as current)
| URL | What | When | Why superseded |
|---|---|---|---|
| https://clay-engine-5rf291nb7-r0am.vercel.app/day-one | Day One questionnaire | 25 Aug | Leftover URL; use Rev 5 `pyve0t08w` |
| https://clay-engine-refdzwbzh-r0am.vercel.app/lab/… | 28 Aug pre-call Roadmap/90-Day | 28 Aug 11:29 | Package `fbxmjk9uh` is the team URL |
| https://clay-engine-meby0cm31-r0am.vercel.app/lab/roadmap-review | Weekly Tactical 25 Aug | 24 Aug | Older hash |
| https://clay-engine-cbx9tek3u-r0am.vercel.app/lab/90-day-plan-v4 | same | 24 Aug | Older hash |
| https://clay-engine-7w1w4ykw7-r0am.vercel.app/lab/orientation | Orientation first pass | 24 Aug | Not on 31 Aug finish-line list |
| https://clay-engine-1tvpufaz2-r0am.vercel.app/lab/landing-v4-directions/instrument?close=aoki | Pre-prod Instrument | 21 Aug | joinclay.com is production |
| https://clay-launch-overview-yanoapps-projects.vercel.app/ | Launch Overview | 25 Aug tactical | **UNVERIFIED** this run |

## Decks / docs in review
| Artifact | Link | Modified | Owner | Status |
|---|---|---|---|---|
| **Brand deck to Deven** | — | asked 31 Aug Slack | Ryan | **Not on Drive.** Outstanding. |
| Partial Brand Manual 08-30-26 | Slack https://clayhc.slack.com/archives/C0BKJJH75KK/p1788199773247319 | 31 Aug 11:09 PT | Deven | Posted after “Your Numbers” kill. Needs Ryan design scrub. Not the missing deck. |
| Partial Brand Manual 08-25-26 | https://drive.google.com/file/d/1RhuGdXw4IN-kp4yeNXDW5VgMJLlWpAj6/view | 27 Aug | ryan@ | Older Drive copy. Do not treat as the Deven deck. |
| intake-rev5-team-review | https://drive.google.com/file/d/1E2oJHWVurqFDU3MSHP0dFl4_OHRkIlFk/view | 27 Aug | ryan@ | Matches Day One footer. |
| 90-day plan adjustments | https://drive.google.com/file/d/1jlSWe7_siKhIyWq55sbsAUmWQoccZKn2/view | 27 Aug | ryan@ | Sleep generic; Lifestyle remove. |
| Brief: Roadmap Review | https://docs.google.com/document/d/1XgtJPvJAgSss6smcuw7_l6rvaKuDysfid7tOwSdBuOs/edit | 12 Aug | alex@ | Older than this week’s Slack. Do not average with 31 Aug shipping. |
| Brief: 90-day Plan | https://docs.google.com/document/d/1KjmbwZpJv2iwsSw6TjxWPMD-ujCAqbCwAed-9NL3CEY/edit | 12 Aug | alex@ | Same vintage warning. |
| Clay Member Journey Flow | https://docs.google.com/document/d/1daznG_ft7JebUGG8dDLxtQI98u2udZqZq4GRimL36_4/edit | 13 Aug | alex@ | Model A. Not today’s naming lock. |
| FUEL intake spec | Gmail `1a03a3d6ea1df1f5` | 25 Aug | Andrew | Still open. Template, not member data. |
| Peptide Tab sacrificial brief | https://drive.google.com/file/d/1rYn79PZooBvkGxYenvYGoOcTV-vjEl6S/view | 31 Aug 1:23 PM | ryan@ | New today. After Thursday. |
| 01_CLAY_BRAND_AND_LANGUAGE_CANON | https://docs.google.com/document/d/1AP62qkb7PXffi63l6P_RJqHEag7RpZfNURDMJEWJXP0/edit | 3 Aug | ryan@ | Canon; not this week’s deck. |
| Open Decisions ledger | https://docs.google.com/document/d/1-iEDiUrHlWrXDzqouvTwt3tnQwUlxax_l0oJ-RnDCgw/edit | 3 Aug | ryan@ | None of 20 items marked closed. |

## Slack asks of Ryan (open / this week)
| Ask | Who | When | Link | Status |
|---|---|---|---|---|
| Remaining Roadmap + 90-Day + one package | Ryan self; Alex dated Thu | 31 Aug | https://clayhc.slack.com/archives/C0BH6TA333M/p1788201698264549 | In flight. Package live. |
| Intake Thursday; welcome text/email today | Alex | 31 Aug 10:21 | https://clayhc.slack.com/archives/C0BH6TA333M/p1788196870300649 | Open. |
| Notion MCP path A/B/C | Alex | 31 Aug 1:54 PM | https://clayhc.slack.com/archives/D0BHP5NESBZ/p1788209672731559 | **Open — today.** |
| Granola Next Steps | Alex | 28 Aug | https://clayhc.slack.com/archives/D0BHP5NESBZ/p1787936985913649 | Treat open until Thursday package proves them. |
| 90-Day Loom | Alex | 28 Aug | https://clayhc.slack.com/archives/D0BHP5NESBZ/p1787937391497069 | Open (90-Day not reviewed on 28 Aug call). |
| Restore Movement/Protocols/Sleep | Alex | 28 Aug | https://clayhc.slack.com/archives/C0BKJJH75KK/p1787943179127849 | Partial — Ryan 31 Aug claims restored. |
| Clay-role draft for Roadmap slide 3 | Ryan → Deven | 28 Aug | https://clayhc.slack.com/archives/C0BKJJH75KK/p1787942387898119 | Open unless closed off-Slack. |
| Brand deck | Ryan self | 31 Aug | same studios post | Asked; **file not on Drive**. |
| Design scrub of brand manual | Deven | 25 Aug + 31 Aug files | https://clayhc.slack.com/archives/C0BKJJH75KK/p1787719353135899 | Open. |
| joinclay.com remaining scrub + phone | Deven / Rajiv | 25 Aug | Deven GDM + Rajiv DM | Open. Site already live. |
| Texting-number logo contrast | Joel | 27 Aug | https://clayhc.slack.com/archives/C0BH6TA333M/p1787867336140849 | Open. |

## Gmail (not send)
| Thread | Date | Ask | Action |
|---|---|---|---|
| `1a058addbb518d01` Follow-up from Friday | 31 Aug | Laurel old HubSpot forms; Gorman UX + Vibrant PDF | Intake Thursday. **Skip Vibrant PDF.** |
| `1a03a3d6ea1df1f5` FUEL recs questionnaire | 25 Aug | Andrew questions | Fold into Intake/Fuel. |
| `1a04a4238a603a15` Clay Meeting | Tue 1 Sep 8:00–8:45 AM PT | Aaron + Justin + Ryan | Prep packet. |
| `1a044a724100bfd1` Failed production deployment | 27 Aug | R0AM one-off | **Closed.** Do not treat as open incident. |
| `1a024af847c0c312` Tech / AI strategy | 21 Aug | Rajiv weekly; Ryan CC | Series status **UNVERIFIED**. |
| Deven 1:1 | — | Canceled (Drive/Gmail sweep) | Do not prep a Deven 1:1. Brand-deck send is still the Slack ask. |

## Figma
Canonical master **unconfirmed**. July playground `3QtmIKzGcNVHNDUrqt2h7e` is **not canon**. Ignore LIVEGRID. Opened read-only: June landing `rKZIh5hAg0yxiqu4xnvba7` (archive). **No current Figma ask this week.** Current review surface is Vercel, not Figma.

## GitHub
`clayhc/clay-engine` and `claylife/clay-engine` 404 to this identity. FORGE has no GitHub destination for clay-engine until the product org repo is visible.

Reachable `rroaam` draft PRs — all **#1**, all stale **31 Jul ~2:49 PM PT**, all still draft:
- `rroaam/clay-ops` #1 chore/repo-governance → main
- `rroaam/clay-hq` #1 same
- `rroaam/joinclay-site` #1 LEGACY banner (site frozen; last GH update 31 Jul; `feat/v5-*` is not the live engine)
- `rroaam/roam-os` #1 LEGACY README

Aug 26–28 review deploys (`feat/external-review-package-2026-08-28`, etc.) exist only as Vercel CLI `gitCommitRef`, **not** pushed to `roam-os`. No new R0AM `clay-engine` deploys after Fri 28 Aug 2:31 PM PT (`fbxmjk9uh` is still latest). No clones. No merge.

## Recommended review order for Ryan
1. https://clay-engine-fbxmjk9uh-r0am.vercel.app/review/external-package — Thursday send.
2. Field Record on that package (prototypes only).
3. Day One Rev 5 → Thursday Intake (call it Intake).
4. https://joinclay.com remaining production scrub (not a new cutover).
5. Brand deck — **missing file**; Deven 08-30-26 manual is the naming source, not the deck.
6. https://clay-monday-review-closeout-2026-08.vercel.app/review/monday-creative-sprint — **dated closeout, not Thursday send.** Four Deven brand gates + asset rights still block external share. Do not use its Sep-30/550 GTM calendar as this week’s queue.

## Last-mile (do not do from this queue)
Send Slack as Clay, send the brand deck, merge, change production aliases, connect live member data.
