# HOUR — FORGE implementation packet (live preview only)

**Written:** 2026-08-31 ~2:28 PM PT  
**Amended:** 2026-08-31 ~2:27 PM PT — do not start from rroaam/roam-os.  
**Agent:** FORGE  
**Ask:** Packet so FRAME’s three can land the moment a PAT exists. Source = live Vercel HTML/CSS this hour. No clone. No GitHub retry. No new product repo. No production.

**Status:** Packet ready. Still no writable `clay-engine`. Idling.

Canonical spec: `TEST_06_FRAME.md` (the three). Ignore `context/TEST_06_PACKAGE_ALT_HUB_FIGMA.md`.

**Do not start from `rroaam/roam-os`.** Vercel R0AM `clay-engine` git-links that repo, but it is **legacy Roam OS** (no `/review`, no `/lab`). The live package on this host is a **Codex CLI dirty upload**; SHA `fa9ae693` is **not** in roam-os. `clay-hq` / `clay-ops` / `joinclay-site` remain off-limits. No CloudAgent. No clone. Land only when a real product repo that actually contains this preview is writable.

---

## Live host (this hour)

| | |
| --- | --- |
| Package host | https://clay-engine-fbxmjk9uh-r0am.vercel.app |
| Hub | `/review/external-package` |
| Deploy | `dpl_33Jsa4c38PZADDXgW9P1UcGDyh2n` |
| Build id (HTML comment) | `flOBFZCLJtETkVRTVQbFp` |
| `x-matched-path` (hub) | `/review/external-package` |
| Title | `Clay Connected Review Package` |
| Method | `user-Vercel` `web_fetch_vercel_url`. No clone. No source maps recovered (JS chunk fetch failed). |

Sister host used only to confirm filled Roadmap overlay (package-host `fixture=full` HTML truncated before `<main>`):  
`https://clay-engine-geubcggc7-r0am.vercel.app` · `dpl_7Xr2Xp5tP59en3MwBonBRZF7ACP5` · `?fixture=full&experience=guided` → `data-review-state="filled-mock"`.

---

## Visible assets (not invented source files)

Do **not** invent `app/review/external-package/page.tsx`. Hub HTML had no `page-*.js` chunk (prerendered). RSC children were `["","review","external-package"]` — that is a **route**, not a file path.

**Hub CSS module (complete, this hour):**  
`/_next/static/css/4b75f4cbc7b5d1de.css?dpl=dpl_33Jsa4c38PZADDXgW9P1UcGDyh2n`  
Also loaded: `12d9c1e13c760012.css`, `98d0b12c69843914.css`.

**Script `src` visible in artifact HTML (App Router chunk paths only):**

- `/_next/static/chunks/app/lab/artifact-styling-lab/roadmap-review/page-850239b3016f3d81.js`
- `/_next/static/chunks/app/lab/artifact-styling-lab/90-day-plan/page-9f687dea69cf51cd.js`

Those prove the **routes** `/lab/artifact-styling-lab/roadmap-review` and `/lab/artifact-styling-lab/90-day-plan`. They do not prove a `.tsx` filename.

No `sourceMappingURL` recovered. **No other file-path guesses.**

---

## 1. Hub — current DOM

`body.bg-paper.font-sans.text-charcoal`

```
main.page_page__sd_Wn
  header.page_topbar__4Kunw
    “External review package · August 28, 2026”
  section.page_hero___Rybq
    p.page_eyebrow__DufsL          “Connected experience review”
    h1                             (NO class)
                                   “One member journey.” + <br/> + “Three connected artifacts.”
    div.page_heroAside__rWgmP
      p
      div.page_pills__PYfhZ[aria-label="Review boundaries"]
        span “Synthetic data”
        span “No real connections”
        span “Not member-final”
  section.page_artifacts__oIzdC[aria-labelledby="package-title"]
    div.page_sectionHeading__984r_
      p.page_eyebrow__DufsL        “Recommended walkthrough”
      h2#package-title             “Start inside. Finish with the member.”
    div.page_artifactList__0GlTI
      article.page_artifactRow__XTx8T × 3
        span.page_index__niZwg
        div.page_artifactCopy__tYNQq
          span.page_eyebrow__DufsL
          h3
          p
        div.page_artifactAction__Yb7sm
          span   (status)
          a      “Open review ↗”
  section.page_lower__jD3X_
    nav.page_directLinks__NSjm4
  section.page_boundary__yIb8o
  footer.page_footer__kGoti
```

### Current cards (selectors to change)

| Index | Eyebrow (`span.page_eyebrow__DufsL`) | `h3` | Status (`div.page_artifactAction__Yb7sm > span`) | `a[href]` |
| --- | --- | --- | --- | --- |
| `01` | Staff workflow | Clay Field Record | Synthetic demo · APIs later | `/ops/member-record?section=overview` |
| `02` | Member conversation | Roadmap Review | Filled mock · review only | `/lab/artifact-styling-lab/roadmap-review?fixture=full&experience=guided` |
| `03` | **Approved handoff prototype** | 90-Day Plan | Filled mock · review only | `/lab/artifact-styling-lab/90-day-plan?state=filled-mock&experience=guided` |

H1 selector: `section.page_hero___Rybq > h1` (unstyled class; rules live on the parent).

Direct links already on hub (`nav.page_directLinks__NSjm4 a`):

- `/ops/member-record?section=uploads`
- `/ops/member-record?section=blood`
- Roadmap `#blood-review-first` and `#blood-complete-panel` (full + guided)
- `/lab/artifact-styling-lab/guide-library`

**No fixture strip on the hub today.** Hub CTAs deep-link only filled mocks.

---

## 1b. Hub — current CSS (exact rules to restyle)

Tokens on `main.page_page__sd_Wn`: `--paper:#f7f4ec; --ink:#171513; --muted:rgba(23,21,19,.62); --line:rgba(23,21,19,.14);`  
(Artifact CSS uses `--ast-ink:#121110`. Do not mix unless asked.)

```css
.page_hero___Rybq{
  display:grid;
  grid-template-columns:minmax(0,1.5fr) minmax(300px,.7fr);
  gap:clamp(48px,8vw,130px);
  align-items:end;
  padding:clamp(70px,10vw,150px) 0 clamp(74px,10vw,145px);
}
.page_hero___Rybq h1,.page_hero___Rybq>.page_eyebrow__DufsL{grid-column:1}
.page_hero___Rybq h1{grid-row:2}
.page_hero___Rybq h1{
  max-width:12ch;
  margin:18px 0 0;
  font-size:clamp(58px,7.5vw,118px);
  font-weight:520;
  line-height:.88;
  letter-spacing:-.07em;
}
.page_artifactList__0GlTI{border-top:1px solid var(--line)}
.page_artifactRow__XTx8T{
  display:grid;
  grid-template-columns:56px minmax(0,1fr) minmax(210px,.4fr);
  gap:28px;
  align-items:start;
  min-height:210px;
  padding:32px 0;
}
.page_artifactRow__XTx8T+.page_artifactRow__XTx8T{border-top:1px solid var(--line)}
.page_artifactCopy__tYNQq h3{
  margin:13px 0 0;
  font-size:clamp(30px,3vw,48px);
  font-weight:530;
  line-height:1;
  letter-spacing:-.04em;
}
.page_artifactAction__Yb7sm{display:grid;justify-items:end;gap:28px;text-align:right}
.page_artifactAction__Yb7sm a{
  display:inline-flex;min-height:44px;align-items:center;gap:14px;
  padding:0 17px;border:1px solid var(--ink);border-radius:99px;
  color:var(--ink);font-size:12px;font-weight:600;text-decoration:none;
}
@media (max-width:820px){
  .page_hero___Rybq,.page_sectionHeading__984r_,.page_lower__jD3X_,.page_boundary__yIb8o{grid-template-columns:1fr}
  .page_artifactRow__XTx8T{grid-template-columns:38px minmax(0,1fr)}
  .page_artifactAction__Yb7sm{grid-column:2;justify-items:start;text-align:left}
}
@media (max-width:520px){
  .page_hero___Rybq h1{font-size:52px}
  .page_artifactRow__XTx8T{grid-template-columns:28px minmax(0,1fr);gap:12px}
  .page_artifactAction__Yb7sm a{width:100%;justify-content:space-between}
}
```

Hub is **already** not a 3-up card row at 390: stacked list at ≤820px. Hierarchy change is **order + copy + extra fixture `<a>`s**, not a new grid.

---

## 1c. Hub — what to change (FRAME three #1)

Selectors only. Copy from FRAME; do not invent clinical claims. Reuse on-page boundary paragraph.

| Target | Current | Change |
| --- | --- | --- |
| `section.page_hero___Rybq > h1` | “One member journey. Three connected artifacts.” | Sequential member path (Roadmap → 90-Day), not three-equal. Keep `max-width:12ch` or widen if the new line wraps badly. |
| `h2#package-title` + sibling eyebrow | “Start inside. Finish with the member.” / “Recommended walkthrough” | Member-path heading. Real H1/H2/H3 order (FRAME a11y). Do not rely on `01/02/03` alone. |
| `div.page_artifactList__0GlTI` article order | 01 Field Record · 02 Roadmap · 03 90-Day | Primary: Roadmap then 90-Day. Field Record **out of this list** (or last, labeled staff). |
| Card 03 `span.page_eyebrow__DufsL` | “Approved handoff prototype” | Qualify or remove. CTA stays “Open review”, not “Approved”. Boundary copy already says mocks do not imply clinical/copy/production approval. |
| `nav.page_directLinks__NSjm4` | Blood / uploads / Guide Library | Staff rail: Field Record + existing Blood links + Guide Library. |
| New fixture `<a>`s | None on hub | Add under `div.page_artifactAction__Yb7sm` (or a new strip beside it) using **working query params below**. Do not invent a new badge language. |

Pills `div.page_pills__PYfhZ` stay (Synthetic data / No real connections / Not member-final).

---

## 2. Fixture query params that already work (HTTP 200 this hour)

Package host unless noted. `data-review-state` is on `main.ast-doc`.

| Artifact | Query | HTTP | `data-review-state` | Overlay (`::before` on `.ast-slide`) |
| --- | --- | --- | --- | --- |
| Roadmap | `?fixture=full&experience=guided` | 200 (hub already links; package-host HTML truncated before `<main>`; **geubcggc7** same query = `filled-mock`) | `filled-mock` (confirmed on geubcggc7) | `MOCK DATA · DESIGN REVIEW` |
| Roadmap | `?fixture=partial&experience=guided` | 200 | `internal-reference` | `INTERNAL REFERENCE · NOT FOR MEMBERS` |
| Roadmap | `?fixture=kickoff&experience=guided` | 200 | `internal-reference` | same |
| 90-Day | `?state=filled-mock&experience=guided` | 200 | `filled-mock` | `MOCK DATA · DESIGN REVIEW` |
| 90-Day | `?state=pending&experience=guided` | 200 | `internal-reference` | `INTERNAL REFERENCE · NOT FOR MEMBERS` |
| 90-Day | `?state=empty&experience=guided` | 200 | **`internal-reference`** | same (guided empty does **not** use `empty`) |
| 90-Day | `?state=empty` (no `experience`) | 200 | **`empty`** | **none** — CSS has no `data-review-state='empty'` overlay rule |

**Hub must expose (FRAME):** Roadmap `partial` + `kickoff`; 90-Day `pending` + `empty`. All four HTTP 200 on this host.

**Param trap:** `state=empty&experience=guided` ≠ `state=empty`. For a true empty overlay-less fixture, link `state=empty` **or** add a CSS overlay for `empty` (none exists live). For Thursday walkthrough in guided chrome, `pending`/`kickoff`/`partial` already paint the internal-reference overlay.

CSS overlay rules (inlined on `main.ast-doc`, live):

```css
.ast-doc[data-review-state='filled-mock'] .ast-slide::before{
  content:'MOCK DATA · DESIGN REVIEW';
  position:absolute; right:32px; top:43px; z-index:9;
  color:currentColor; opacity:.72;
  font:10px/15.5px 'Geist Mono','Courier New',monospace;
  letter-spacing:1.4px; text-transform:uppercase;
}
.ast-doc[data-review-state='internal-reference'] .ast-slide::before{
  content:'INTERNAL REFERENCE · NOT FOR MEMBERS';
  position:absolute; right:32px; top:43px; z-index:9;
  max-width:260px; color:currentColor; opacity:.72;
  font:10px/15.5px 'Geist Mono','Courier New',monospace;
  letter-spacing:1.2px; text-align:right; text-transform:uppercase;
}
```

Document-level only. No per-slide `data-review-state`. Per-slide attrs that **do** exist: `data-field='dark'|'image'`, `data-goal-chrome='guided'`.

---

## 2b. Empty / partial / pending — existing hooks (reuse, do not plot zeros)

Live CSS (inlined on guided pages this hour). Use these; do not draw a zeroed pentagon.

| Hook | What it does |
| --- | --- |
| `.gxr-pending` (+ `strong` + `span`) | Circular placeholder, not a dial. Copy slots already sized. |
| `.gxl-ledger-row[data-state='pending'] .gxl-ledger-copy` | Quiet copy color |
| `.gxl-ledger-row[data-state='empty'] .gxl-ledger-copy` | Quiet copy color |
| `.gxr-point[data-copy-complete='false']` | Quiets finding + recommendation |
| `.ast-artifact-radar-score-value[data-pending='true']` | Score becomes 9px mono uppercase, not a number |
| `.ast-artifact-radar-pending` | Pending panel (strong + p) |
| `.ast-pending` | Dashed empty box (strong + p) |
| `.ast-five-summary-row[data-state='pending'|'empty']` | Quiet table copy |
| `.ast-plan-coverage-item[data-state='pending'|'no-action'|'unmapped']` | Quiet coverage cells |

**Existing fixture chrome on artifact pages (CSS, not on hub):**

```css
.ast-screen-nav{
  position:sticky; top:12px; z-index:50;
  display:flex; flex-wrap:wrap; gap:8px;
  width:min(1056px,100%); margin:0 auto 18px; padding:8px;
  border:1px solid rgba(18,17,16,.11); border-radius:99px;
  background:rgba(251,250,244,.92); backdrop-filter:blur(12px);
}
```

Reuse `.ast-screen-nav` around the stage for the guided fixture strip. Do not put the strip inside `.ast-slide`. Hub strip is new: extra `<a>`s in `.page_artifactAction__Yb7sm` or `.page_directLinks__NSjm4` (both already exist).

`::before` overlay is not a live text node. FRAME a11y: empty/pending need an equivalent **in-flow** fixture name. `data-review-state` is already on `<main>`.

Styling-lab index on this host (`/lab/artifact-styling-lab`) **failed** MCP this hour (“Unable to create shareable URL”). Nav labels Full / Partial / Empty · Pending / Filled / Empty are documented on the 26 Aug host in FIELD `TEST_02_PREVIEWS.md` — not re-fetched here.

---

## 3. 90-Day alignment-open — use existing overlay + in-flow kicker

**Do not delete chapters. Do not write dosing copy.**

Live overlay is **whole-document**: `main.ast-doc[data-review-state='internal-reference']` paints every `.ast-slide`. Setting filled-mock’s `<main>` to `internal-reference` would overlay goal / Five Elements / ownership too. That is **not** what FRAME asked.

What to add (no new badge language):

1. **In-flow chapter kicker** on Protocols / Movement / Fuel targets / Sample Week/Day. Reuse the live overlay string: `INTERNAL REFERENCE · NOT FOR MEMBERS` (Geist Mono, already the `::before` content). FRAME’s alt `ALIGNMENT OPEN · NOT MEMBER-FINAL` is **new copy** — only use if Ryan prefers it; live CSS does not contain it.
2. Optionally set `data-review-state="internal-reference"` on **those slides only** if the CSS is extended from `.ast-doc[…]` to `.ast-slide[data-review-state='internal-reference']::before`. That selector **does not exist live**. Do not assume it.

### Classes confirmed in live CSS for those chapters

| Chapter (FRAME name) | Live classes seen | Notes |
| --- | --- | --- |
| Sample Week / Day | `.gpr-body` `.gpr-week-list` `.gpr-day-list` `.gpr-week-row` `.gpr-day-row` `.gpr-panel-heading` | 7-row week list; day list uses `--gpr-day-count`. |
| Fuel targets | `.ast-targets` `.ast-target-strip` `.ast-target` `.ast-target-lower` `.ast-target-guardrails` | Macro strip is 5 columns. |
| Protocols / Movement | **not named in the truncated HTML** | Do not invent a class. Find by slide heading text once source is writable. Nearby unmapped templates in the same CSS: `.ast-relay`, `.ast-snapshot`, `.ast-spotlight`, `.ast-plan-coverage`. |

Locked-enough chapters (goal, Five Elements decisions, ownership, Sleep) stay `filled-mock` overlay `MOCK DATA · DESIGN REVIEW`.

Pending 90-Day (`state=pending&experience=guided`) already whole-docs as `internal-reference`. Do not preview protocol names there.

---

## Landing sequence (when PAT exists)

**Not `rroaam/roam-os`.** Vercel’s git-link is a false friend. Wait for a writable product repo that actually contains this preview (SHA `fa9ae693` is not in roam-os). Then: isolated `review/` branch. Draft PR. Preview only. No merge. No production alias/env. No CloudAgent until that repo is named.

1. Hub copy + card order + fixture `<a>`s (selectors above). Qualify/remove “Approved handoff prototype”.
2. Hub + `.ast-screen-nav` fixture strip: Roadmap `full|partial|kickoff`, 90-Day `filled-mock|pending|empty` using the working queries. Empty: decide `?state=empty` vs `?state=empty&experience=guided` (they map to different `data-review-state`).
3. Empty/partial: `.gxr-pending` / `data-state='pending'|'empty'` / `data-copy-complete='false'` / `.ast-artifact-radar-pending`. Never plot missing as zero.
4. Alignment-open: in-flow kicker with existing overlay string; do not delete Protocols / Movement / Fuel / Sample Week/Day.

---

## What this packet is not

- Not a clone, not a PR, not a preview deploy, not a CloudAgent.
- Not `rroaam/roam-os` (legacy Roam OS; Vercel git-link is stale vs this preview).
- Not GitHub until a product repo that contains SHA `fa9ae693` / this `/review` + `/lab` surface is writable (`HOUR_FORGE.md`).
- Not UI on `clay-ops` / `joinclay-site` / `clay-hq`.
- Not a new product repo.
- Not production.
- No PHI.
- No invented `.tsx` paths.

**Production impact:** none.
