# TEST 02 — Member journey product-state brief

**FIELD** · 2026-08-31 ~2:00 PM PT · one page  
**Canon check:** `HUMAN DECISION` — no locked member journey. Four models coexist. Slack/previews are not canon.  
**Evidence pack:** `context/TEST_02_SOURCES.md` + `context/TEST_02_PREVIEWS.md` (live Slack/Drive/Gmail/Vercel this afternoon). No PHI. Nothing sent.

---

## Member goal

A joined member can complete context capture, sit Baseline, receive a clinical picture, walk a Review, leave with a 90-day path, then live on Clay (check-ins, re-baseline). **That spine is intended, not locked.** Current operational intake is still old HubSpot forms; designed surfaces are review prototypes on separate R0AM branches.

---

## Current vs proposed

| Layer | What exists now (evidence) | What this week is acting as |
|---|---|---|
| Live ops | Laurel HubSpot `/client-intake-form` + `/join-clay-99`. joinclay.com purchase funnel (21 Aug, untouched). | Keep running until Thursday Intake pass replaces it — **not confirmed**. |
| Spoken sequence (31 Aug, Deven + Justin) | baseline assessment → baseline review → roadmap & 90 day plan | Newest leadership/clinical alignment. **Not written** into Alex Flow or the 3 Aug ledger. |
| Shipping package (Ryan, `#clay-studios` 31 Aug) | Three connected **prototypes**: Field Record (staff) → Roadmap Review (member conversation) → 90-Day Plan (handoff). URL: `https://clay-engine-fbxmjk9uh-r0am.vercel.app/review/external-package` | Finish-line week artifact set. Synthetic / not member-final / no live data. |
| Alex Flow (Drive, modified 13 Aug) | Welcome → Intake 1.9 → Pre-Baseline Coach Call → Baseline Assessment → **internal Clinical Review** → Baseline Report **includes** Roadmap (annual) → Review Session **co-builds** 90-Day Plan → live the plan → re-baseline | Still the newest written journey draft. Conflicts with shipping names. |
| Aug 3 NotebookLM pack | 9 phases. Clinical Read kept **distinct**. Roadmap vs 90-Day = **PRODUCT DECISION REQUIRED**. Ledger 20 items, none closed. Last written 3 Aug. | Working canon on paper. Stale vs 31 Aug Slack. Do not silently close. |
| Justin “first four” swimlane (5 Aug) | Initiation / Discovery / Review and Guidance / Action and Execution. Public page chrome only this pass. | Parallel CX model. Ryan 8/11 claimed it closed taxonomy — **contradicted** by 31 Aug naming fights. |

**Proposed (this week’s working picture, labeled inference):** Day One / Intake (designed) → Baseline visit → internal clinical synthesis → Roadmap Review + 90-Day Plan as two artifacts in one visit package → staff Field Record as the capture/handoff workspace → portal/ongoing later. Do not treat this as approved.

---

## Confirmed (evidence)

- **No production member journey app.** Six seed previews HTTP 200; all `target: null` feature branches 26–28 Aug. Pages say review-only, synthetic, no persistence / EHR / CRM / Supabase / member delivery.
- **Day One ≠ `/intake` on the same host.** `/day-one` = Day One Intake Rev 5 (you + medical picture, ~7 min, Start, tab-only). Same host `/intake` = pre-join Apply/fit (Begin; “production flow ships on the funnel”). Laurel’s live forms are HubSpot, not either route.
- **Field Record is a staff workspace**, not a member portal. `/ops/member-record`: 12 sections; Active Baseline demo; Day One complete / Baseline in progress; 90-Day **blocked** until a versioned Roadmap handoff. `/portal` on that host **404**.
- **Roadmap Review and 90-Day Plan are two lab routes** with empty/partial/filled (Roadmap `full|partial|kickoff`; 90-Day `pending|filled-mock|empty`). Filled Roadmap copy: 90-Day “arrives after this review.” Filled Roadmap also says the Roadmap refreshes at every Baseline and the 90-day Plan inside it is rewritten every 90 days — **conflicts** with Alex Flow (Roadmap annual).
- **Empty/partial/filled is review-fixture logic only.** Incomplete inputs “fail closed without invented content” (Ryan 28 Aug). Partial radar must not plot missing as zero (26 Aug lanes note). No production empty-state for a real member.
- **Thursday 3 Sep:** Alex — 90-Day to the team; next Intake Form for Studios review. Gorman UX notes + Laurel HubSpot URLs landed today (synthesis remaining). Andrew FUEL recs questionnaire (25 Aug) still open yes/no.
- **HPH partnership** is a parallel inquiry track, not a journey stage. Mapping of inquiry → member still missing (Ryan 24 Aug).

---

## Incomplete

- Clinical Read: no `/clinical-read` (404 on Day One host); no heading on Field Record / Day One / Roadmap lab. Named on pearl marketing HTML as step 03 and in Aug 3 pack (concept + email 8 + possible portal item).
- Member portal / ongoing Field Record for members: not observed. Aug 6 `portal-v3` preview not re-fetched this pass.
- Day One questions / medical-picture / receipt screens: intro only (Start not clicked).
- Roadmap `partial`/`kickoff` and 90-Day `pending` pages: nav exists; not walked this pass.
- Auth, persistence, consent, booking, messaging, EHR, uploads for real members: **explicitly not connected**. Do not invent.
- Open Decisions ledger (3 Aug) never updated. Baseline contents, Clay Score, emails 01–10, portal PHI still open on paper.
- Deven Partial Brand Manual 08-30-26 posted in Slack; “Your Numbers” correction **not verified** in file.
- `CLAY_AI_ACCESS` Drive folder: not found. Product GitHub org: 404. Notion/Granola/Calendar: not connected.

---

## Inconsistencies (do not average)

| Conflict | A | B | C |
|---|---|---|---|
| Roadmap vs 90-Day | Alex Flow + 10 Aug Ryan: two artifacts; Roadmap **inside** Baseline Report, annual; 90-Day co-built same visit | 20 Aug briefs + 31 Aug package: two named artifacts, Roadmap Review **then** 90-Day | Brand/landing: one step “Roadmap and 90-Day Action Plan.” Aug 3 ledger still PRODUCT DECISION REQUIRED |
| Clinical Read | Aug 3: distinct member-adjacent concept | Alex Flow: **internal** Clinical Review | 4 Aug LP public How It Works; 31 Aug shipping **omits** it |
| Visit names | Alex Flow: Baseline Report Review Session | Deven/Justin 31 Aug: baseline review | Shipping artifact title: Roadmap Review. Brand error: Your Numbers |
| Intake names | Product: Intake Form | Review route: `/day-one` (existing `/intake` untouched) | Preview title historically “Your Baseline Questions.” Live: HubSpot |
| 90-Day size / prescription | Ryan 28 Aug: six slides, not overly prescriptive | 26 Aug NotebookLM PDF counts 10/39/10; 31 Aug package includes Sample Week/Day, Movement, Protocols, Sleep | Ryan 31 Aug blocker: how prescriptive (protocols/movement/nutrition). 26 Aug: Lifestyle **removed**; Sleep generic (Andrew owns wording) |
| Care-team title | Open Decisions: Medical Lead + Clay Guide locked; coach unresolved | 90-Day brief hedges Health Guide / coaching call / Vitality Guide | Deven 25 Aug joinclay: Health Guide. Pulse Checks → Regular Check-Ins |
| Field Record | 31 Aug Slack + connected package only | Aug 3 Member Portal + Upload Records | Aug 6 portal-v3; 27 Aug failed prod `clay-staff-member-record` — **do not collapse** |

---

## UX / product decisions needed

Owner types. None of these are closed by a prototype.

1. **Product + clinical + leadership:** Lock the member sequence and write it back to the Open Decisions ledger. Candidate (spoken 31 Aug, not approved): Baseline assessment → baseline review → Roadmap + 90-Day. Decide whether Clinical Read is a member artifact, an internal step, or retired public copy.
2. **Product:** Roadmap vs 90-Day — one artifact vs two. If two: is Roadmap annual (Alex Flow) or refreshed at every Baseline (filled Roadmap copy)?
3. **Product + ops:** Intake source of truth for Thursday — Day One Rev 5 vs Laurel HubSpot vs Gorman UX notes (goal-first, “why we ask,” end on named guide + booked session) vs Andrew FUEL spec. Day One vs `/intake` vs Apply funnel naming.
4. **Product + clinical:** How prescriptive is the 90-Day Plan (protocols, movement, nutrition)? Andrew Sleep wording + FUEL yes/no.
5. **Product + UX:** Field Record vs Portal vs staff member-record — one staff workspace, a member dashboard, or both? Uploads first pass is prototype only.
6. **Brand + product:** Care-team title (Health Guide vs Coach vs Vitality Guide vs Health Pro). “Your Numbers” vs “Roadmap Review.”
7. **Product + legal/eng:** Portal auth / PHI / real uploads (ledger 12–13). Blocked for production until clinical/legal.
8. **Product:** HPH inquiry → member mapping. Do not fold into Intake without a source.
9. **UX:** Empty/partial/filled vocabulary for trainings vs live member states. Fail-closed is stated for fixtures only.

---

## Ready for design (FRAME)

Reviewable as **labs**, not as locked product:

- Connected package walkthrough (28 Aug) + synthetic boundary copy.
- Roadmap guided filled mock + fixture switches (full/partial/empty).
- 90-Day guided filled mock + pending/empty switches. Sleep generic / Lifestyle removed (26 Aug brief) still need visual confirmation.
- Day One Rev 5 intro; Apply `/intake` intro (different product).
- Field Record IA: 12 sections, status dots, Five Elements lanes, blocked handoff — staff workflow prototype.
- Gorman UX notes are **input** for Thursday Intake, not a spec.

**Do not hand FRAME a single journey IA** until decisions 1–3 above. PAPER owns Roadmap/Plan artifact presentation once requirements stabilize.

---

## Ready for build (FORGE)

**Not ready as product.** Pages say so.

Build-adjacent only (review branches, `target: null`): `feat/external-review-package-2026-08-28`, `feat/staff-member-record-2026-08-27`, `feat/guided-artifact-experience-2026-08-28`, `review/day-one-intake-rev5-2026-08-26`. 27 Aug R0AM **production** attempt `clay-staff-member-record-…-3MCG` failed (email unread; later previews READY — do not promote).

FORGE can keep **review-branch** work: fixture states, fail-closed empty, Day One tab-only, Field Record demo switcher. Do **not** wire persistence, CRM, EHR, member delivery, or production aliases.

---

## Required data / ops

- Thursday Intake synthesis owner: Alex (form) + FRAME/FIELD (UX) using Gorman notes + HubSpot current + Rev 5. Do not open Vibrant PDF.
- Andrew: Sleep wording; FUEL questionnaire ingest; workout spec yes/no.
- Ops: current live HubSpot forms remain until a replacement is named.
- Portal/Field Record: no live member data; do not enter real records in the demo.
- Welcome SMS / call outlines still lack a named source (24 Aug). Out of this brief’s journey lock, still a Day One adjacency.

---

## Last-mile approvals needed

Human: lock journey taxonomy (ledger item 4 + Clinical Read + intake name); 90-Day prescriptiveness; care-team title; any production Field Record / portal / Day One. Clinical/legal: Baseline contents, real uploads, PHI/auth. **Not this sprint:** send, publish, merge to main, production deploy, identifiable PHI.

**Handoff:** FRAME — do not design a unified journey chrome until product locks 1–3. FORGE — review-branch only. PROOF — four-model conflict + ledger vs Slack. PAPER — Roadmap/90-Day artifact presentation after the one-vs-two lock.
