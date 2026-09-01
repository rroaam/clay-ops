# HOUR — FIELD Intake Form fold

**FIELD** · 2026-08-31 ~2:35 PM PT  
**Language this pass:** **Intake Form** (not Day One). Review route still `/day-one`.  
**Canon check:** `HUMAN DECISION` — no locked member journey. Four models stay unmerged.  
**Evidence pack:** `context/HOUR_INTAKE_SOURCES.md` (Drive Rev 5 + preview JS + HubSpot SSR + Gmail Laurel/Gorman/FUEL).  
**Skipped:** Vibrant PDF (PHI; not opened, not used as a question source). No invented questions. Nothing sent. Preview not clicked through.

---

## Member goal

A person who is joining Clay can give the team a **goal-first picture of themselves**, a **medical picture the provider can use before the draw**, and **records/pictures of what they already have** — then land with a **named person and a next session**, not a dead end. That is Gorman’s intended close plus Laurel’s ops need. **It is not locked.** Live ops still run on two old HubSpot forms that do not collect that picture.

---

## Current vs proposed

| Layer | Current (evidence today) | Proposed this pass (fold only — not a lock) |
|---|---|---|
| Live ops | Two **old** HubSpot forms (Laurel 11:13 PT, Gmail — **not** this-morning Slack). `client-intake-form` = 25 admin/legal/contact fields, **Submit**. `join-clay-99` = same 25 fields + Core Experience / $599+$99 copy, **Continue to Payment**. **No records/pictures fields** on either public form. | Keep HubSpot running until a replacement is **named**. Do not treat Slack “Laurel still a blocker for the URL” as current. |
| Designed Intake Form | Rev 5 review at `https://clay-engine-pyve0t08w-r0am.vercel.app/day-one` (HTTP 200, tab-only, nothing saved). Splash still says **Day One**. 13 personal + 6 medical shipped; **B12 withheld**. Camera/upload disabled in review. | Thursday talk = **Intake Form**. Keep `/day-one` as the review route. Do not rename production this hour. |
| Same-host `/intake` | Different product: **Apply** (11 questions, “production flow ships on the funnel”). Did not click Begin. | **Out of this fold.** Do not merge Apply into Intake Form. |
| Mid-form artifact | Rev 5 four panels (Why / what you’re going after / how you want to be worked with / Clay team: Advisor, Medical Lead, Member Services + the call). **No graph, no letter grade, no score.** Panel 3: no label/type/score/chart. | Gorman wants a **start-picture** (Noom projection / Superpower letter) into Blueprint/Roadmap. **Conflict.** Do not add a grade. |
| End state | Rev 5 end card: “You just told us what a good life looks like for you.” Save this + Done. **No name, no date, no next step.** HubSpot: “watch email/texts for follow-up from your Clay Guide” (ops, not a booked session). | Gorman: **named guide/physician + booked Health Guide session**. **Conflict.** Booking/auth/persistence unspecified. Do not invent a booker. |
| FUEL | Andrew 25 Aug: template `FUEL_Basics_Intake_Spec_questions.docx` would frame FUEL recs from inputs; “not as accurate as Inbody and post review.” **Questionnaire items NOT RECOVERED** (Gmail has no attachment download; Drive has no copy). Workout/training spec is an unanswered yes/no. | Coaching/recs template, **not** a replacement member Intake Form. Do not invent items. Do not put recs on Field Record (staff). |
| Field Record | Staff workspace. `/portal` 404 last TEST 02. | Stays staff. Intake Form is member-facing. |

**Proposed working picture (labeled inference, not approved):** one **Intake Form** that keeps Rev 5’s existing goal-first + medical questions, uses HubSpot only for live identity/consent/payment until replaced, treats photos as **records + med/supplement bottles only**, and treats Gorman’s preview/end as **UX requirements on the existing artifact/end card** — not new questions. Four journey models remain unmerged.

---

## What can be folded (sourced — no new questions)

Fold means: map onto an **existing** Rev 5 screen or name an ops/UX requirement. It does **not** mean add a question.

1. **Call it Intake Form.** Rev 5 product language in Drive/preview is still “Day One.” Thursday pass uses Intake Form. Route `/day-one` stays the review URL.
2. **Goal-first is already B1 → B2** (chips, cap 3, then rank). Gorman “start with goal setting” does **not** add a new goal question. Do not duplicate Apply Q2/Q3 into this form.
3. **Laurel “records and pictures, no other photos”** maps onto existing **B13 / B14** (photo of bottles; type-instead allowed) and **B16** (labs/records/imaging/photo of a report). **Do not add** selfies, body photos, or extra camera screens. Public HubSpot forms have **zero** upload fields as rendered today — Laurel’s claim is **ops intent, not a live HubSpot field**.
4. **Two HubSpot forms are the live intake**, not a new form. `client-intake-form` = non-charging / insurance-style admin (assignment of benefits, card auth, Submit). `join-clay-99` = member/Core Assessment track (Continue to Payment). Fold as **current ops**, not as Thursday’s question set.
5. **Gorman “medical as personalization”** maps onto the existing part-break: “A few minutes of medical detail so your provider has it before your draw.” Do not rewrite B20/B21/B13–B16 into new asks.
6. **Gorman “why we ask” on every contraindication** is a **microcopy requirement**, not a new question. Rev 5 B12 has **no microcopy by design** and is **withheld** until an automatic provider-alert path exists. Do **not** invent why-we-ask lines. Do **not** ship B12 in this review.
7. **Optimal ranges live in CLAY Brain**, not in the skipped Vibrant PDF, and **not in Intake Form**. Out of this fold (Blood / Roadmap).
8. **Andrew FUEL email intent** (starting-place recs from inputs; Inbody + post-review is more accurate) can sit as a **post-intake coaching input**, not as member questions this hour. Workout spec stays unanswered.

---

## What cannot be folded — HUMAN DECISION

Owner types. Do not average. Do not resolve in this file.

| # | Decision | Owner | Why it is still open |
|---|---|---|---|
| 1 | Which surface is Thursday source of truth: live HubSpot vs Rev 5 Intake Form vs same-host Apply `/intake` | **Product + ops** | Three different products. HubSpot = 25 identity/consent fields, 0 clinical questions. Rev 5 = 13+6 clinical/personal. Apply = 11 fit questions. |
| 2 | One Intake Form vs two tracks (insurance/non-charge vs $599+$99 member) | **Product + ops** | Laurel sent both URLs as “the old forms.” join-clay-99 is a payment CTA. Rev 5 has no payment, no DOB/sex/address, no emergency contact. |
| 3 | Where identity/consent/payment live once HubSpot is replaced | **Product + legal + eng** | Rev 5 has B19 reachability only. HubSpot has TOS, treatment, benefits, card, PHI share, emergency contact. Auth/persistence/CRM write **not connected**. |
| 4 | B12 ship vs withhold | **Clinical + eng** | Spec: only if platform auto-alerts provider. Preview JS: omitted because routing is not connected. Do not invent the alert path. |
| 5 | Mid-form “start-picture”: keep 4-panel observations vs add Noom graph / Superpower letter into Blueprint/Roadmap | **Product + UX** | Rev 5 Panel 3 explicitly has no label, type, score, or chart. Gorman wants a preview graph/letter. Adding a grade would be **invented scoring**. |
| 6 | End card: Rev 5 “no next step” vs Gorman named guide/physician + booked Health Guide session | **Product + ops + eng** | Booking, calendar, named-staff assignment, consent to show a name: **unspecified**. HubSpot only promises a later Guide text/email. |
| 7 | Care-team titles on the artifact | **Product + brand** | Rev 5: Advisor / Medical Lead / Member Services + the call. Gorman: guide/physician + Health Guide. Slack still treats coach title as open. Do not average. |
| 8 | FUEL questionnaire items, once recovered: inside Intake Form, after it, or coaching-only | **Product + clinical (Andrew)** | Items **NOT RECOVERED**. Email says starting-place, less accurate than Inbody. Do not invent. |
| 9 | Andrew workout/training spec: yes or no | **Andrew / product** | Email offer. Unanswered. |
| 10 | Member journey lock | **Leadership + product + clinical** | Four models unmerged (Alex Flow 13 Aug, Aug 3 ledger, Justin swimlane, 31 Aug spoken sequence). Spoken 31 Aug is not written into Alex Flow. Out of Intake Form except as context. |

---

## Question inventory (exact text in sources — not restated here to avoid drift)

| Surface | Member-visible asks | Notes |
|---|---|---|
| Rev 5 personal | **13** (B1–B6, B8–B11, B17–B19). No B7. | Goal-first already. B8 advisor-facing only. |
| Rev 5 medical spec | **7** | Preview ships **6**. **B12 withheld**. |
| Apply `/intake` | **11** | Different product. Do not fold. |
| HubSpot client-intake-form | **25** fields, 4 steps | Admin/legal/contact. **0** clinical. **0** uploads. |
| HubSpot join-clay-99 | **25** fields + Core Experience block | Same fields; 2 facilities not 4; **Continue to Payment**. **0** uploads. |
| Andrew FUEL spec | **0 recovered** | Gap. |
| Gorman | **0 questions** | 4 UX constraints only. |

Do not copy Apply sleep/energy/train/labs wording into Intake Form. Thematic overlap with B1/B9/B15 is not a license to merge copy.

---

## UX requirements for FRAME

Requirements on **existing** Rev 5 screens. No new question list. Visual work waits until decisions 1, 5, 6 are stable enough to draw.

- Keep B1 → B2 as the open. Do not add a second goal screen.
- Medical part-break already frames personalization. Add a **why-we-ask line slot** on contraindication screens (B12 if it ever ships; B20; B21). **Copy is unwritten** — do not invent the lines in Figma.
- Mid-form artifact: keep the four observation panels until product picks graph vs letter vs current panels. **Do not draw a Superpower-style grade** as if it were sourced.
- End card: current = universal close, no name, no date. Gorman wants named person + booked Health Guide session. **Draw as an open end-state**, not as shipped UX, until booking exists.
- Photos: bottles (B13/B14) + records (B16) only. No extra photo chrome.
- Preview splash still says Day One. If FRAME touches chrome this week, **Intake Form** is the talk-track; do not silently retitle production.
- Field Record stays off the member path.

Hand visual once 1 / 5 / 6 have a human call. PAPER owns Roadmap/Plan artifact presentation, not this Intake Form mid-form card.

---

## Build requirements for FORGE

**Not ready as product.** Review branch only (`review/day-one-intake-rev5-2026-08-26`). `target: null`.

- Keep tab-only; camera/upload stay disabled until a real upload path exists.
- Keep **B12 omitted** until an automatic provider-alert path is named and built.
- Do not wire HubSpot replacement, CRM write (B1 tags), persistence, booking, or named-staff assignment.
- Do not merge Apply `/intake` into `/day-one`.
- Do not implement FUEL recs scoring from a missing spec.
- Engine write is currently **blocked** (`clayhc/clay-engine` 404 to this identity). A green preview would not be production approval.

---

## Required data / ops

- **Live:** Laurel’s two HubSpot URLs remain the operational intake until product names a replacement. Gmail 11:13 PT is current for those links; this-morning Slack is not.
- **Records/pictures:** Laurel says they ask; public forms as fetched today do **not** have the fields. Ops needs to say whether that happens **off-form** (email, in-clinic, Guide follow-up) or was never implemented on these two forms.
- **Andrew:** recover `FUEL_Basics_Intake_Spec_questions.docx` (not on Drive; Gmail MCP cannot download). Until then, zero FUEL items.
- **Vibrant / Blood organization:** still skipped. Optimal ranges → CLAY Brain, not Intake.
- **CRM / portal object for the Rev 5 artifact:** unspecified. Do not invent.

---

## Last-mile approvals needed

Human: Thursday source of truth (decision 1); one form vs two tracks (2); end-state booking (6); care-team titles (7); FUEL placement once items exist (8).  
Clinical: B12 path (4); why-we-ask medical copy; any member-facing clinical claim.  
Legal: HubSpot consents vs Rev 5 (treatment, benefits, card, PHI share).  
**Not this hour:** send, publish, merge to main, production alias, identifiable PHI, journey lock.

---

## Preview URL (review only — untouched this hour)

https://clay-engine-pyve0t08w-r0am.vercel.app/day-one  

HTTP 200. `noindex`. Stamp `2026-08-26-intake-rev5-team-review`. Did **not** click Start. Questions recovered from Drive spec + shipped JS (see sources). Same-host `/intake` is Apply — out of fold.

Live HubSpot (ops, not Thursday send):

- https://clayhealthandcare-48923784.hs-sites.com/client-intake-form  
- https://clayhealthandcare-48923784.hs-sites.com/join-clay-99  

Did **not** submit. Labels only.

---

## Evidence vs inference

**Evidence:** Rev 5 question set (Drive `1da3nGoPXUpHk9MDlNrs_1EeK6IFVTqTa` + JS); B12 withheld; HubSpot 25+25 field labels via public SSR; Laurel “old forms” + records/pictures/no other photos; Gorman four UX constraints; FUEL email intent; preview splash copy; no upload fields on HubSpot as rendered.

**Inference (do not upgrade):** one Intake Form that keeps Rev 5 questions and treats HubSpot as a temporary identity/consent shell; photos-off-form as the explanation for Laurel vs HubSpot gap; FUEL as post-intake coaching.

**Not found:** FUEL question items; HubSpot file-upload fields; provider-alert path; booking path; named-staff assignment; journey lock.

**Handoff:** FRAME — wait on 1/5/6; why-we-ask is a slot, not copy. FORGE — review-only, B12 stays out. PAPER — Roadmap/Plan, not this form. PROOF — three-product collision (HubSpot / Rev 5 / Apply) + Gorman end-state vs Rev 5 end card.
