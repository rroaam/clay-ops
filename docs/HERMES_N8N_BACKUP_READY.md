# Clay Autonomous Backup Stack — Ready for Review

Built: 2026-08-31
Host: `Ryans-Mac-mini.local`
Built to: `docs/CLAY_BACKUP_STACK_OPERATOR.md`

A local Hermes + n8n stack that runs the Clay bot roster on the Mac mini, in parallel with
GrokBot. GrokBot was not modified.

**Update 2026-09-01:** the team access layer is built on top of this stack. Ryan, Alex, Justin,
and Deven reach the system through NORTH in Slack over Socket Mode, with no public inbound port.
See `docs/TEAM_ACCESS_STATUS.md`. It is staged and tested; creating the Slack app is the one
remaining human step.

---

## 1. Machine and environment inventory

| | |
|---|---|
| macOS | 26.6.2 (build 25G83), arm64 |
| Hostname | `Ryans-Mac-mini.local` |
| Disk | 460 GB volume, 20 GB free after the build (31 GB before; the n8n image accounts for the difference) |
| Homebrew | 6.0.18 |
| Docker | Engine 29.6.2 via Docker Desktop |
| Node / npm / pnpm | v22.23.2 / 10.9.8 / 11.18.0 |
| Python / uv | 3.14.6 / 0.12.1 |
| git | 2.55.0 |
| Claude Code | 2.1.252 |
| Codex CLI | 0.146.1 |

At preflight the Docker daemon was not running and Docker Desktop's `AutoStart` was disabled.
Both were corrected. See §9.

---

## 2. Hermes

| | |
|---|---|
| Version | Hermes Agent **v0.21.0 (2026.8.31)** — updated during this build from v0.19.1 (2026.7.30) |
| Install | `~/.hermes/hermes-agent` |
| Python | 3.11.15 |
| Default model | `claude-sonnet-5` (Anthropic) |
| Health | `hermes status` clean; `hermes -p north cron status` reports the gateway running with a live ticker heartbeat |

The install was 4 weeks stale at preflight (v0.19.1, 2026-08-03) against upstream tag
`v2026.8.31`. Updated via the official `hermes update` path after a full 240 MB backup. The
update carried the roster forward intact — all nine `SOUL.md` role identities, all fifteen Clay
skills, the launchd gateway, and the three cron jobs survived — and seeded 10 new and 30 updated
bundled skills into every Clay profile. Capabilities verified, each exercised during the build:

- **persistent named bots** — `hermes profile create`, nine profiles created
- **preserved memory and state** — per-profile `SOUL.md`, `.env`, memory, and session store
- **terminal and filesystem tools** — used by every smoke test
- **scheduled routines** — `hermes cron`, three jobs created and firing
- **delegation between bots** — `hermes kanban` plus the delegate tool; profile descriptions are
  set so the kanban decomposer routes by role rather than by name

Backups taken before any change, to `~/ClayHQ-Automation/backups/2026-08-31T160759/`:
Hermes `config.yaml`, `SOUL.md`, `auth.json`, `.env`, and the Docker Desktop settings file.

---

## 3. n8n

| | |
|---|---|
| Version | 2.36.9 Community Edition |
| Image | `docker.n8n.io/n8nio/n8n:latest` |
| Container | `clay-n8n` |
| Bind | `127.0.0.1:5678` — loopback only, not reachable from the network or the internet |
| Restart policy | `always` |
| Persistence | `~/ClayHQ-Automation/n8n/data` bind mount (SQLite, credentials, logs) |
| Health check | `curl -s http://127.0.0.1:5678/healthz` → `{"status":"ok"}`; container reports `(healthy)` |
| Owner account | `ryan@designwithroam.com`, signed in 2026-08-31; all six workflows owned by his personal project |
| Encryption key | generated locally into `~/ClayHQ-Automation/n8n/.env`, chmod 600, gitignored |

Telemetry, version notifications, templates, and personalization are disabled. No credentials
are committed to Git.

---

## 4. Exact local paths

```
~/ClayHQ-Automation/              working root
├── AGENTS.md                     shared Clay working context, injected from the cwd
├── RUNBOOK.md                    start / stop / restart / logs / health
├── bin/                          clay-sync-souls, clay-sync-skills
├── bots/ROSTER.md                the nine bots and how to talk to them
├── clay-ops/                     rroaam/clay-ops checkout
├── config/
│   ├── clay_shared_context.md    source spine, authority order, design brain, autonomy model
│   └── roles/*.md                one role file per bot
├── skills/clay/                  the 15 Clay shared skills (source of truth)
├── n8n/
│   ├── docker-compose.yml
│   ├── .env                      encryption key, chmod 600, gitignored
│   ├── data/                     n8n persistent state
│   ├── files/intake/             serialized NORTH intake packets
│   └── workflows/*.json          the six workflow definitions
├── state/                        decisions.md, asset_ledger.md, packets, approvals, worktrees
├── reports/smoke/                smoke-test transcripts
├── logs/
└── backups/2026-08-31T160759/    pre-change backups

~/.hermes/profiles/<bot>/         per-bot profile, SOUL.md, skills
~/.hermes/scripts/clay_intake_drain.sh
~/Library/LaunchAgents/ai.hermes.gateway-north.plist
~/dev/clay-engine                 claylife/clay-engine checkout
~/.grokbot                        GrokBot — untouched
```

---

## 5. Bot roster

Nine persistent Hermes profiles, each with its own role identity in `SOUL.md`, its own memory
and session state, and the full Clay skill layer.

| Bot | Role | Launcher |
|---|---|---|
| NORTH | Chief of Staff / Orchestrator | `north` |
| FIELD | Product + Member Experience | `field` |
| FRAME | Digital Product Designer | `frame` |
| STUDIO | Brand + Content Studio | `studio` |
| FORGE | Design Engineer | `forge` |
| PROOF | Canon + Claims + QA | `proof` |
| PAPER | Roadmap / 90-Day / Clinical Read / decks | `paper` |
| VOICE | Governed copy, lifecycle, microcopy | `voice` |
| SIGNAL | Competitive research, GTM, partnerships | `signal` |

Role text is versioned in `config/roles/` and compiled into each `SOUL.md` together with the
shared Clay context by `bin/clay-sync-souls`. Edit the config, not the profile.

Every bot inherits the design execution context: quiet, premium, evidence-led, human; neutral
fields with imagery and data carrying color; Geist and Geist Mono; the Clay grounds; no generic
SaaS grids, no decorative green chrome, no glow, glass, or random gradients; one surface profile
at a time; no averaging of conflicting design eras.

---

## 6. Skills created

Fifteen Clay skills, authored in Hermes's native `SKILL.md` format with YAML frontmatter, under
the `clay` category. Installed into all nine profiles and confirmed `enabled` by
`hermes -p <bot> skills list`.

`clay-canon-check` · `clay-task-packet` · `clay-digital-ui-ux` · `clay-brand-studio` ·
`clay-artifact-design` · `clay-copy-language` · `clay-image-generation` ·
`clay-video-generation` · `clay-asset-governance` · `clay-design-to-code` · `clay-preview-qa` ·
`clay-research-pack` · `clay-approval-packet` · `clay-decision-capture` ·
`clay-weekly-review-prep`

Source of truth is `~/ClayHQ-Automation/skills/clay/`. `bin/clay-sync-skills` reinstalls them.

---

## 6b. Curated third-party skill layer

After the roster was working, the skill registries were surveyed and a **deliberately small**
set added per role. The selection rule was trust, not popularity — see the security note below.

| Bot | Added | From |
|---|---|---|
| NORTH | `one-three-one-rule`, `watchers`, `duckduckgo-search`, `internal-comms` | Nous official, Anthropic |
| FIELD | `adversarial-ux-test` | Nous official |
| FRAME | `concept-diagrams`, `frontend-design`, `webapp-testing` | Nous official, Anthropic |
| STUDIO | `creative-ideation`, `algorithmic-art` | Nous official, Anthropic |
| FORGE | `pinggy-tunnel`, `docker-management`, `code-wiki`, `webapp-testing` | Nous official, Anthropic |
| PROOF | `adversarial-ux-test`, `webapp-testing` | Nous official, Anthropic |
| PAPER | `concept-diagrams`, `pptx-author`, `doc-coauthoring`, `canvas-design` | Nous official, Anthropic |
| VOICE | `doc-coauthoring`, `internal-comms` | Anthropic |
| SIGNAL | `duckduckgo-search`, `searxng-search` | Nous official |

The `hermes update` itself also added ten genuinely relevant bundled skills to every bot:
`competitor-news-monitor`, `sdlc-review`, `github`, `email-inbox-triage`,
`document-to-action-items`, `meeting-action-items`, `weekly-review-planning`,
`blocked-page-recovery`, `product-price-monitor`, `box`.

### The capability this actually unlocked

**SIGNAL could not search the web at all.** No Tavily, Firecrawl, Browser Use, or Browserbase
key is set, so a research bot had no research tool. `duckduckgo-search` plus the `ddgs` CLI
(installed via `uv tool install ddgs`) is keyless and free. Verified live in smoke Test H:
SIGNAL produced a cited competitive pack on Function Health, Superpower, and InsideTracker,
correctly separated observed facts from company claims, flagged one source as a rival's claim
about a rival, reported a tool quirk honestly (`ddgs -o json` returns empty, plain text works),
and routed to NORTH as INFORMATION without inventing positioning.

### Security note — why the selection is small

The agent-skill registries are an active supply-chain target. Public reporting through 2026
documents the **ClawHavoc** campaign poisoning ClawHub with hundreds of malicious skills using
typosquatted names and delivering the Atomic macOS Stealer; ClawHub removed thousands of
suspicious entries and added VirusTotal scanning. An independent study found roughly **37% of
agent skills carry at least one security flaw and 13% at least one critical issue**.

This machine holds the Anthropic API key, a GitHub token with **admin on `claylife/clay-engine`**,
and Clay canon. Bulk-installing community skills onto it would be reckless, so:

- Every skill installed came from **`official`** (Nous-published, trust `builtin`) or
  **`anthropics/skills`** (vendor-published, trust `trusted`).
- **Zero** skills were installed from ClawHub, skills.sh community indexes, or any
  `community`-trust source.
- Anthropic's `brand-guidelines` skill was deliberately **skipped** — it applies *Anthropic's*
  brand, which is exactly wrong for a Clay bot. Relevance was checked per skill, not assumed.
- `hermes security audit` (OSV.dev) → **no known vulnerabilities across 137 components**.
- `hermes skills audit` per profile → **0 HIGH or CRITICAL** findings after pruning. The one HIGH
  it raised beforehand was a false positive: a prose "pitfalls" line in an unrelated TouchDesigner
  skill mentioning `sudo chmod` in documentation, not code. That skill was removed as irrelevant
  rather than whitelisted.

### Pruning

Each bot had grown to ~99 skills, most irrelevant (LLM fine-tuning, Philips Hue, Polymarket,
ASCII video). `bin/clay-prune-skills` removes a documented denylist from the nine Clay profiles
and leaves the `default` profile alone. Result: 99 entries removed across the roster, skills
index down from 10.2 KB to 8.3 KB of a 40 KB system prompt.

The point is signal-to-noise, not bytes. A brand bot should not have `pokemon-player` in its
index competing for attention with `clay-brand-studio`.

**`hermes update` re-seeds bundled skills, so re-run `bin/clay-prune-skills` after every update.**

---

## 7. Workflows and routines

### n8n workflows

| Workflow | ID | State | Endpoint / schedule |
|---|---|---|---|
| Clay Slack Signal Watch | `iUKhtT8bQ2lGzuUm` | active | `POST /webhook/clay/slack` |
| Clay Email Work Watch | `n6BANsdHe6LP5iw8` | active | `POST /webhook/clay/email` |
| Clay GitHub Review Watch | `Ijh3LD41LeF5Byr6` | active | `POST /webhook/clay/github` |
| Clay Notion Change Watch | `lHwL386hA9cEoWgx` | **disabled, AUTH_REQUIRED** | `POST /webhook/clay/notion` |
| Daily Clay Autonomous Workday | `mZ9iNDWZUfTp4z4w` | active | `0 8 * * 1-5` |
| Site Improvement Lab | `8pDoa8ANxlp4v4BR` | active | `0 9 * * 2,5` |

Each watch classifies a signal as DECISION, REQUEST, FEEDBACK, BLOCKER, INFORMATION, or NOISE,
assigns a priority lane by scored match against `context/ACTIVE_PRIORITIES.md`, and serializes
anything meaningful into a NORTH intake packet. Noise is dropped: no packet, no notification.
GitHub routes technical items to FORGE with NORTH copied.

### Hermes cron routines

| Job | Schedule | Purpose |
|---|---|---|
| `clay-intake-drain` | `*/15 * * * *` | Feeds new intake packets to NORTH. Silent when idle. |
| `clay-daily-workday` | `0 8 * * 1-5` | Reconcile, pick at most three reversible tasks, delegate, route to PROOF. |
| `clay-site-improvement-lab` | `0 9 * * 2,5` | FRAME + FIELD + FORGE + PROOF review current surfaces on review branches. |

### Why the split

n8n runs in Docker and cannot reach the host Hermes binary. n8n is the event and schedule layer;
Hermes on the host is the execution layer. They meet at one shared folder,
`~/ClayHQ-Automation/n8n/files/intake`. Packets move `NEW` → `PICKED`. There is no polling loop
and no busy-wait: webhooks are event-driven and the drain is a 15-minute cron that exits silently
with no output when there is nothing new.

---

## 8. Connectors

### Authenticated and working

| Connector | Evidence |
|---|---|
| Anthropic API | Hermes `claude-sonnet-5`; every smoke test ran on it |
| OpenAI API | key present in Hermes env |
| OpenRouter | key present in Hermes env |
| GitHub (`gh`, identity `rroaam`) | scopes `gist, read:org, repo, workflow`; **admin on `claylife/clay-engine`** |
| Local Git to `claylife/clay-engine` | fetch and `ls-remote` succeed |
| Local Git to `rroaam/clay-ops` | fetch and push succeed |
| **Web search (keyless)** | `ddgs` CLI installed; SIGNAL returned a cited competitive pack in Test H |
| **n8n owner account** | Ryan signed in 2026-08-31 as `ryan@designwithroam.com`; all six workflows are owned by his personal project `PLNpEVCfzUU3Q6h8` |

### AUTH_REQUIRED

| Connector | What is needed | Impact |
|---|---|---|
| **Slack** | For the team access path this is now the only step left: create the NORTH Slack app from the committed manifest and paste two tokens. No tunnel is involved. See `docs/TEAM_ACCESS_STATUS.md` §10. The separate n8n signal-watch workflow still needs its own Slack credential in n8n. | NORTH is staged and disabled until its tokens exist; the n8n watch is live and testable but receives no real events |
| **Email** | A Gmail or IMAP credential in n8n, then swap the webhook trigger for the mail trigger | Same: live and testable, no real mail |
| **GitHub webhooks** | Register a webhook on `claylife/clay-engine` and `rroaam/clay-ops` against a reachable URL | `gh` CLI already has the scope to register one; blocked only on a public URL |
| **Notion** | A Notion credential for the Clay workspace | Workflow ships **disabled** on purpose |
| **Google Drive** | Not connected from this stack | The Drive briefs in `SOURCE_INDEX.md` cannot be read automatically |
| **Figma** | Current canonical master still unidentified for this identity | FRAME works from code, not Figma |
| **Vercel** | Not configured in this stack | Preview deployments are not driven from here |

Nothing was purchased, no permissions were changed, and no credential was entered on anyone's
behalf.

---

## 9. Persistence

| Service | Starts | Survives reboot |
|---|---|---|
| Hermes gateway (NORTH) | launchd user agent `ai.hermes.gateway-north`, installed with `--start-on-login` | yes |
| n8n | Docker Compose `restart: always` + Docker Desktop `AutoStart` enabled | yes |

Two changes were needed and both were made:

1. The compose file originally used `restart: unless-stopped`. A full Docker Desktop quit and
   relaunch left the container **stopped**, because `unless-stopped` does not start a container
   that the daemon had stopped. Changed to `restart: always`.
2. Docker Desktop's `AutoStart` was `False`, so the engine would not come back at login. Set to
   `True`. The previous settings file is in the backup directory.

Both were then verified by quitting Docker Desktop entirely and relaunching it. n8n came back on
its own within 10 seconds, re-activated all five published workflows, and served a live webhook
request afterwards. The Hermes gateway was unaffected throughout.

Start, stop, restart, log, and health commands for both services are in
`~/ClayHQ-Automation/RUNBOOK.md`.

---

## 10. Local Clay repositories discovered

Forty-odd Git repositories under `~/dev`. The Clay-relevant ones:

| Path | Remote |
|---|---|
| `~/ClayHQ-Automation/clay-ops` | `https://github.com/rroaam/clay-ops.git` |
| `~/dev/clay-engine` | `https://github.com/claylife/clay-engine.git` |
| `~/dev/clay-knowledge` | `https://github.com/rroaam/clay-knowledge.git` |
| `~/dev/_IMAC_GIT_RECOVERY_2026-08-03/clay-ops` | local recovery bundle |
| `~/dev/_IMAC_GIT_RECOVERY_2026-08-03/clay-engine__dashboard` | local recovery bundle |
| `~/dev/_IMAC_GIT_RECOVERY_2026-08-03/clay-hq-precopy-backup-2026-07-28` | local recovery bundle |

No repository was deleted, renamed, migrated, or reset.

---

## 11. `clay-engine` remote and access findings

**This is the most consequential finding of the build.**

`context/REPO_ACCESS_GAP.md` records that the automation identity gets a 404 on
`claylife/clay-engine`. **That gap does not apply to this Mac mini.** Verified directly:

```
gh api repos/claylife/clay-engine
  → claylife/clay-engine | private=true | default=main
  → permissions: {"admin":true,"maintain":true,"pull":true,"push":true,"triage":true}
gh auth status → rroaam, scopes: gist, read:org, repo, workflow
```

`origin/main` HEAD is `ee83dff179d1b42b32926d292de7397caf6dba9f`, dated 2026-07-02.

All four branch/commit receipts in the context pack were checked and **all exist**:

| Branch | Recorded commit | Result |
|---|---|---|
| `feat/artifact-morning-review-2026-08-26` | `f186c91e…` | commit exists; branch tip has since moved to `29164bfe…`, recorded SHA is an ancestor |
| `review/day-one-intake-rev5-2026-08-26` | `ee18036a…` | exists, still the branch tip |
| `review/instrument-brand-delta-2026-08-26` | `7a55e220…` | exists, still the branch tip |
| `review/instrument-team-media-alt-2026-08-18` | `696f552f…` | exists, still the branch tip |

`DESIGN.md` is present on `origin/main`. **`docs/DESIGN_AUTHORITY.md` is absent from
`origin/main`** but present on 34 other branches, including all four recorded ones. The
authority order in `DESIGN_EXECUTION_CONTEXT.md` puts `docs/DESIGN_AUTHORITY.md` first, so
anyone resolving authority from `main` alone will not find the top-ranked source. Worth a human
decision.

`main` is also materially stale: it predates all the 2026-08-26 review work, which lives only on
unmerged feature branches. That is a separate issue from the Grok/Cursor access gap, and it is
not explained by it.

The local working tree at `~/dev/clay-engine` is on `feat/flexjet-onepager` @ `0d3a055` with 17
dirty files. **It was not touched.** Same branch, same HEAD, same dirty file count before and
after the build.

FORGE recorded these findings on a review branch in `clay-ops`,
`review/repo-access-confirmed-2026-08-31` @ `3b720a8`, which updates `REPO_ACCESS_GAP.md` from
`MISSING_ACCESS` to a **scoped** confirmation: confirmed for `rroaam` on this machine, still open
for the Grok/Cursor identity. That branch is pushed for review and is **not** merged.

---

## 12. Smoke-test results

Full transcripts are in `~/ClayHQ-Automation/reports/smoke/`.

| Test | Bot | Result | What it actually did |
|---|---|---|---|
| A | NORTH | **PASS** | Read `context` in README order, produced current priorities with file-and-line evidence, independently checked `clay-engine` access rather than trusting the context pack, proposed three reversible delegations |
| B | FIELD | **PASS** | Reconstructed the member journey from three non-identical live models, found **seven** unresolved conflicts with dated receipts on both sides, refused to pick one, escalated to NORTH |
| C | FRAME | **PASS** | Declared surface profile Web, read `review/instrument-brand-delta-2026-08-26` via `git show` without checking it out, found three copy-authority departures from locked product terms with file and line, proposed no redesign |
| D | STUDIO | **PASS** | Produced a Social concept resting on shipped code (`CheckoutClient.tsx`), named every open human gate, generated no assets, invented no claims |
| E | FORGE | **PASS** | Branched off `main`, updated `REPO_ACCESS_GAP.md` from real verification, ran the repo's real checks, **reported failures honestly**, did not merge, did not push, left `clay-engine` untouched |
| F | PROOF | **PASS** | Independently re-verified claims from A–E against the real repos and caught three genuine citation errors the other bots made |
| G | n8n | **PASS** | 13 mock Slack, email, and GitHub events injected; all 13 classified correctly, 4 noise dropped silently, 9 NORTH intake packets written with correct routing and priority lanes |
| H | SIGNAL | **PASS** | Live web search after the skill-layer build: cited pack on three real Clay comps, observed separated from claimed, a biased source flagged, a tool quirk reported honestly, routed as INFORMATION without inventing positioning |

### What PROOF caught

PROOF did the job it exists for. Spot-checking A–E against the real sources, it found:

- NORTH presented a phrase as a verbatim quote from `REPO_ACCESS_GAP.md` that is not in the file
- FIELD described `origin/main` as "five weeks stale" when the real gap is about 8.5 weeks
- STUDIO attributed a shipped copy line to commit `ad48a9d`, which is not an ancestor of
  `origin/main`; the line reaches `main` through an earlier commit

None of the three changes the underlying conclusions, and PROOF said so. All three are recorded
rather than quietly fixed. This is the behavior the roster is supposed to have: bots make
citation mistakes, and the gate catches them before a human sees the work as source-of-record.

### Real defects the roster surfaced

Found while testing, not introduced by it:

1. **`clay-ops` test suite has 7 failing tests.** `uv run pytest` → 143 passed, 7 failed.
   `uv run clay-ops validate` fails with `CANON_UNRESOLVABLE`. Root cause:
   `config/canon-registry.json` points at `../clayhc-clay-engine`, a path that does not exist on
   this machine; the real clone is `~/dev/clay-engine`. Needs a decision: repoint the registry,
   relocate the clone, or symlink. Not fixed here — it is outside an access-verification task
   and it touches how canon resolves.
2. **`docs/DESIGN_AUTHORITY.md` is missing from `origin/main`** while sitting first in the
   authority order.
3. **`origin/main` is ~8.5 weeks behind the review work.**
4. **The unified Field Record is not yet unified.** Shipped code on
   `feat/monday-review-closeout-2026-08-31` states plainly that the portal, Field Record, and
   legacy member data layer use different synthetic people and timelines and that "none powers
   the others."

---

## 13. Startup and restart

Full detail in `~/ClayHQ-Automation/RUNBOOK.md`. The short version:

```bash
# Hermes
hermes -p north gateway status | start | stop | restart
hermes -p north cron status          # scheduler health + heartbeat
hermes -p north cron list            # the three Clay jobs
tail -f ~/.hermes/profiles/north/logs/gateway.log

# n8n
cd ~/ClayHQ-Automation/n8n
docker compose up -d | stop | restart | down
curl -s http://127.0.0.1:5678/healthz
docker logs -f clay-n8n

# Talk to a bot
cd ~/ClayHQ-Automation && north chat

# Inject a test event
curl -s -X POST http://127.0.0.1:5678/webhook/clay/slack \
  -H 'Content-Type: application/json' \
  -d '{"event":{"text":"Can you package the Roadmap Review for Thursday?","user":"U","channel":"C","ts":"1"}}'
```

---

## 14. Known limitations

1. **No real event source is connected.** Slack, email, GitHub webhooks, and Notion all need
   either a credential or a publicly reachable URL. The classification and routing layer is
   fully built and tested with injected events, but nothing real flows in yet. This is the
   single biggest gap between "built" and "running."

   FORGE now carries the `pinggy-tunnel` skill, which is the mechanism for the URL half. It was
   **deliberately not run**: opening a tunnel publishes the local n8n to the internet, which is
   a security exposure and a human decision, not a reversible setup choice. The Slack half needs
   a credential regardless.

   **Superseded for the team access path.** NORTH reaches Slack over Socket Mode, which dials
   out and needs no public URL at all, so no tunnel is required to let the team use the system.
   The tunnel question now only applies to the n8n webhook watches. See
   `docs/TEAM_ACCESS_STATUS.md`.
2. **No n8n API key issued yet.** The owner account exists, so one can be created in
   Settings → API. Without it, workflow changes go through the container CLI
   (`docker exec clay-n8n n8n import:workflow`), which cannot update a workflow in place —
   re-importing creates duplicates. Not blocking, just clumsy.
3. **The intake drain is a 15-minute cron, not an event hook.** n8n cannot call the host Hermes
   binary from inside Docker. A webhook listener on the host would make this instant; the cron is
   the reliable version, not the fastest one.
4. **Classification is deterministic regex, not a model.** It is fast, free, predictable, and
   auditable, and it will misfile edge cases. NORTH re-verifies every packet against the context
   pack before acting, so a misfile costs a little attention rather than a wrong action.
5. **One gateway, on NORTH.** Scheduled work is initiated by NORTH, who delegates. The other
   eight bots have no independent scheduler. That matches the orchestration model but means a
   stopped NORTH gateway stops all scheduled Clay work.
6. **Disk is tight.** 20 GB free on a 460 GB volume. The n8n image and Docker's VM take a real
   bite. Worth watching before adding more containers.
7. **`clay-ops` checks do not pass on this machine** — see §12, defect 1. The stack was built and
   tested around a repo whose own validation is failing for a path reason.
8. **Bots make citation errors.** Three in five outputs, all caught by PROOF. Route consequential
   work through PROOF; do not treat a single bot's output as source-of-record.
9. **`docker compose stop` is not sticky.** With `restart: always`, a stopped container returns
   when the Docker engine next starts. Use `docker compose down` to keep it down.

---

## 15. Next recommended improvements

1. **Connect one real event source.** Done for the team access path, pending one human step.
   NORTH now reaches `#clay-studios` and `#joinclay-mvp-landing-page` over Socket Mode with no
   public URL and no tunnel. Create the Slack app from the committed manifest and paste the two
   tokens: `docs/TEAM_ACCESS_STATUS.md` §10. The n8n webhook watches remain a separate question.
2. **Fix `config/canon-registry.json`.** Seven failing tests and a failing `validate` all trace
   to one wrong path. Cheapest high-value fix on the list.
3. **Decide what `main` means in `clay-engine`.** It is 8.5 weeks stale and missing the top
   authority file. Until that is resolved, "current authority" cannot be resolved from `main`,
   and every bot has to be told which branch to trust.
4. **Merge or close the review lanes.** The 2026-08-26 work exists only on unmerged branches.
   That is fine as review posture and expensive as a permanent state.
5. **Give PROOF a machine-checkable copy-law lint.** The locked-term list in
   `language-architecture-sot.md` is exactly the kind of thing that should fail a check rather
   than depend on a bot noticing.
6. **Add a host-side webhook listener** so intake is instant rather than 15 minutes, once a real
   event source is connected and the latency actually matters.
7. **Back up the n8n encryption key** somewhere private before adding any n8n credential. Losing
   it makes stored credentials unrecoverable.
8. **Watch disk.** 20 GB free is enough for now and not for much more.
9. **Re-run `bin/clay-prune-skills` after every `hermes update`.** Updates re-seed the full
   bundled skill set into all nine Clay profiles, undoing the prune.
10. **Keep installing from `official` and `anthropics/skills` only.** The community registries
    are an active supply-chain target; see the security note in §6b. This machine holds the
    Anthropic key and a GitHub admin token.

---

## 16. GrokBot

Untouched. `~/.grokbot` was read once to confirm its location and never written to. Its
`local-exec` daemon was running throughout the build and continued writing its own state files,
which is GrokBot operating normally, not this stack modifying it. No GrokBot process was stopped,
no configuration changed, no file edited or removed.

The default Hermes profile at `~/.hermes` is likewise unchanged: stock `SOUL.md`, original
`config.yaml` timestamps intact. Every Clay change lives in `~/.hermes/profiles/<bot>/`.

---

## 17. Definition of done

| # | Requirement | Status |
|---|---|---|
| 1 | Hermes healthy and usable on the Mac mini | met — v0.19.1, gateway supervised by launchd, live heartbeat |
| 2 | NORTH / FIELD / FRAME / STUDIO / FORGE / PROOF exist and retain their roles | met — plus PAPER, VOICE, SIGNAL; roles held under test |
| 3 | Shared Clay skills installed in Hermes-native form | met — 15 skills, `SKILL.md` format, enabled in all nine profiles |
| 4 | `clay-ops/context` part of the default Clay working context | met — in every `SOUL.md` and in the working-root `AGENTS.md`; all six bots read it unprompted under test |
| 5 | n8n runs locally with persistence | met — 2.36.9, loopback, bind-mounted SQLite, `restart: always` |
| 6 | Autonomous-work and event-routing workflows exist | met — 6 n8n workflows (5 active, Notion disabled pending auth) + 3 Hermes cron routines |
| 7 | Mock-event routing test passes | met — Test G, 13 events, all correctly classified and routed |
| 8 | Six-bot smoke test passes or failures honestly documented | met — A–F all PASS; the three citation errors PROOF caught are documented in §12, not hidden |
| 9 | GrokBot untouched | met — §16 |
| 10 | Completion PR open with full evidence | this document |

---

## 18. What needs a human

1. **Slack, email, and Notion credentials** — the stack is built and tested but no real signal
   flows until one connector is authenticated.
2. **The canon-registry path decision** — repoint, relocate, or symlink.
3. **What `main` means in `clay-engine`** — and where `docs/DESIGN_AUTHORITY.md` should live.
4. **The journey-lock conflicts FIELD surfaced** — seven of them, with receipts on both sides,
   none resolvable without a decision. Details in `reports/smoke/test-B-field.txt`.
5. **Review of `review/repo-access-confirmed-2026-08-31`** — pushed, not merged.

Nothing in this build was merged, deployed, published, promoted, or sent. No purchase was made
and no permission was changed.
