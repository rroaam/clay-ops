# Clay Team Access Status

Built: 2026-09-01
Host: `Ryans-Mac-mini.local`
Extends: `docs/HERMES_N8N_BACKUP_READY.md`

Ryan, Alex, Justin, and Deven can use the Clay AI system from Slack by talking to
NORTH. Nothing about the engine underneath is visible to them: no terminals, no
schedulers, no automation platform, no specialist bots.

**Current state: built, tested, and staged. It is not live yet.** Creating the
Slack app requires a human OAuth session, so it is the one step left. Everything
that leads up to it is done, and §10 is the exact click sequence.

---

## 1. Architecture

```
Clay Slack (clayhc.slack.com)
    ↓  Socket Mode, outbound only
NORTH Slack app
    ↓
NORTH profile on the Mac mini
    ↓  internal delegation
FIELD · FRAME · STUDIO · FORGE · PROOF · PAPER · VOICE · SIGNAL
    ↓
one NORTH reply, in the same Slack thread
```

NORTH is the single front door. The other eight bots have no Slack identity and
no way to acquire one: the manifest defines exactly one bot user, and the
authorization layer recognizes four human beings and nobody else.

**No public inbound port is opened.** The transport is Slack Socket Mode, which
dials out from the Mac mini and holds the connection open. There is no request
URL in the app manifest, no webhook, and no tunnel. Pinggy, ngrok, Cloudflare
Tunnel, and Tailscale Funnel are all unused, and `bin/clay-north-slack-manifest`
fails the build if any of those strings, or a `request_url`, ever appears in the
manifest. Verified on this machine by diffing the full TCP listener list before
and after the change: identical, no new socket.

---

## 2. Identity

Resolved from the Clay Slack workspace directory on 2026-09-01. Nothing is
guessed.

| Person | Slack user ID | Email | Role |
|---|---|---|---|
| Ryan | `U0BH7234V9R` | ryan@designwithroam.com | operator |
| Alex | `U0BJ6DUR2RF` | alex@yano.business | team |
| Justin | `U0BHA0L3C85` | justin@jweniger.com | team |
| Deven | `U0BHB9CDL22` | Deven@clayhealthandcare.com | team |

Workspace: `clayhc.slack.com`.

---

## 3. Authorization

This is a Clay-specific layer, deliberately separate from the ordinary approval
policy in `policies/approval-policy.json`. That policy governs what Clay Ops may
do to a work product. This one governs which human may ask for it, over which
surface, and who has to approve when the asker does not carry the authority.

Everything is edited in one file, `config/team-access.json`. No person, Slack ID,
role, or approver is hard-coded in Python. `src/clay_ops/team_access.py` only
reads and enforces, and it refuses to load a config that references an
unregistered role, capability, surface, or approver.

| Capability | team | operator | Approver when denied |
|---|---|---|---|
| Ask NORTH questions | yes | yes | |
| Request research | yes | yes | |
| Request product, design, or copy work | yes | yes | |
| Request implementation on a review branch | yes | yes | |
| Receive status | yes | yes | |
| Receive previews | yes | yes | |
| Review work and request revisions | yes | yes | |
| Approve production merge or deploy | no | yes | Ryan |
| Approve publishing or external sending | no | yes | Ryan |
| Change access or permissions | no | yes | Ryan |
| Access credentials | no | yes | Ryan |
| Authorize spend | no | yes | Ryan |
| Irreversible deletion | no | yes | Ryan |
| Approve a healthcare or outcome claim | no | **no** | nobody |

Team members default to safe work and review access. Chatting with NORTH grants
no production, external-send, permission-change, credential, spend, or
destructive authority. Ryan retains operator authority over the AI system.

The last row is deliberate. Operating invariant 7 says an unresolved healthcare
or outcome claim never receives clinical approval from Ryan alone, so listing him
as the approver would be wrong. That capability ships with an empty approver list
and returns BLOCKED rather than NEEDS YOUR DECISION, and it says why. When a
clinical claims authority is named, add them to `approvers` in the config file.

Unknown senders are ignored. Not refused, not offered a pairing code, not told
that anything is listening. Enforced twice: at the gateway
(`unauthorized_dm_behavior: ignore` plus `SLACK_ALLOWED_USERS`) and again in the
Clay layer, which creates no work item and returns no reply.

---

## 4. Channel experience

| Surface | Behavior |
|---|---|
| DM with NORTH | Open to the four registered people. No mention needed. |
| `#clay-studios` (`C0BH6TA333M`) | Mention only. Replies go in-thread. |
| `#joinclay-mvp-landing-page` (`C0BHR0BBUEB`) | Mention only. Replies go in-thread. |
| `#clay-north` | Prepared, not created. See §10 step 9. |
| Any other channel | Ignored, even if NORTH is mentioned. |

Normal Clay channels never get flooded. `require_mention` is on for every
approved channel, `ignore_other_user_mentions` keeps NORTH silent when a message
opens by addressing a teammate, and a channel absent from `allowed_channels` is
dropped before anything else runs.

Threads are the unit of work. A follow-up inside an existing NORTH thread
continues the same work item rather than starting a new one, and a new top-level
message never joins an older task. Sessions are separated per user and per
thread, so two people working at the same time never cross.

The dedicated `#clay-north` channel is prepared but not created: making a channel
in the live Clay workspace is Ryan's call, not an automation step. Its row is
already in the config with `enabled: false`. Paste the channel ID, flip the flag,
re-run the sync, and it becomes free-response since the channel exists for NORTH.

---

## 5. Conversation behavior

NORTH remembers who asked. Every work item records requester, Slack channel and
thread, the requested outcome, which specialists were used, status, artifact and
review links, and any decision required.

Work that takes time gets an immediate reply in the thread:

> I'm on it. I'll bring the finished work back here.

Then NORTH works, and comes back to the same thread once. One request produces
one coherent reply, opening with exactly one of:

```
DONE
READY FOR REVIEW
NEEDS YOUR DECISION
BLOCKED
```

Internal agent transcripts are never surfaced. `render_reply` has no parameter
for them, so it is a structural guarantee rather than a habit, and a test asserts
that no specialist name appears in a rendered reply.

### Approvals

When an action needs authority the asker does not have, the useful work is not
thrown away. Everything reversible finishes first, then NORTH names the approver.
Alex asking to ship to production gets the build, the checks, and the review
branch, then:

> Ready. This last step requires approval from Ryan.

---

## 6. Files

Everything below is in `rroaam/clay-ops` on `backup/hermes-n8n-ready-2026-08-31`.

```
config/team-access.json                     the one file you edit
src/clay_ops/team_access.py                 identity, surfaces, authorization
src/clay_ops/work_items.py                  the ledger and the reply contract
src/clay_ops/store.py                       work_items + append-only work_item_events
src/clay_ops/cli.py                         clay-ops team-access … / clay-ops work …
integrations/slack/north-app-manifest.json  the Slack app, Socket Mode
integrations/slack/north-team-access.md     NORTH's behavior contract
bin/clay-north-slack-manifest               regenerate the manifest
bin/clay-north-gateway-sync                 project the config onto the gateway
bin/clay-north-role-sync                    inject the contract into NORTH's role
bin/clay-team-access-acceptance             the eight scenarios, end to end
tests/test_team_access.py                   30 tests
docs/TEAM_ACCESS_STATUS.md                  this file
```

Outside the repository, on the Mac mini:

```
~/ClayHQ-Automation/config/roles/north.md          contract injected between markers
~/.hermes/profiles/north/config.yaml               Slack settings, backed up first
~/ClayHQ-Automation/reports/smoke/team-access-2026-09-01.txt
```

The role file and the gateway config are both generated from the repository, so
neither can quietly drift. `bin/clay-north-gateway-sync --check` and
`bin/clay-north-role-sync --check` report drift and write nothing.

### Commands

```bash
cd ~/ClayHQ-Automation/clay-ops
uv run clay-ops team-access list                    # who has what
uv run clay-ops team-access check --slack-user-id U0BJ6DUR2RF --capability approve_production
uv run clay-ops team-access slack-config            # derived gateway settings
uv run clay-ops work list                           # the ledger
uv run clay-ops work show <work-item-id>            # one item and its history
bin/clay-north-gateway-sync --check                 # config drift
bin/clay-team-access-acceptance                     # the eight scenarios
```

---

## 7. Test results

### Mocked

`tests/test_team_access.py`, 30 tests, all passing. The full suite is 173 passed
and 7 failed, and those 7 are the pre-existing `CANON_UNRESOLVABLE` failures
recorded as defect 1 in `HERMES_N8N_BACKUP_READY.md` §12. They are unrelated to
this work and unchanged by it: the baseline before this change was 143 passed and
the same 7 failed.

### Real

`bin/clay-team-access-acceptance` drives all eight scenarios through the real CLI
against an isolated ledger. Full transcript in
`~/ClayHQ-Automation/reports/smoke/team-access-2026-09-01.txt`.

| # | Scenario | Result |
|---|---|---|
| 1 | Ryan asks a broad project question | PASS. Acknowledged, three specialists used internally, one DONE reply, none of them named. |
| 2 | Alex requests a product/design change | PASS. READY FOR REVIEW with a preview link, in-thread. |
| 3 | Deven gives creative feedback | PASS. READY FOR REVIEW, two directions, no locked terms touched. |
| 4 | Justin asks for current status | PASS. DONE, no delegation needed. |
| 5 | Unauthorized user invokes NORTH | PASS. No reply, no work item, no ledger entry. |
| 6 | Authorized user requests a production deploy | PASS. Reversible work completed, then NEEDS YOUR DECISION naming Ryan. |
| 7 | Two people ask at the same time | PASS. Two work items, two threads, separate specialists, no crossover. |
| 8 | Follow-up inside the original thread | PASS. Resolved to the original work item, requester preserved, history `received → delegated → follow_up`. |

Verified across those runs: identity preserved on every item, tasks stay
separated, specialists delegated internally and never named in a reply,
permissions enforced in both directions, one coherent NORTH response per request,
and no public inbound port.

---

## 8. What is enforced where

| Guarantee | Where |
|---|---|
| Only four people reach NORTH | `SLACK_ALLOWED_USERS` at the gateway, and `TeamAccess.decide` in Clay Ops |
| Unknown senders get silence | `unauthorized_dm_behavior: ignore`, and no work item is created |
| Only approved channels | `allowed_channels`, re-checked by `admits_surface` |
| No channel flooding | `require_mention` on every approved channel |
| One task per thread | `find_work_item_by_thread`, plus per-thread sessions |
| No specialist leaks to Slack | `render_reply` has no parameter for internal output |
| Team members hold no dangerous authority | role grants in `config/team-access.json` |
| History cannot be rewritten | SQLite triggers on `work_item_events`, hash-chained |
| No inbound port | Socket Mode, asserted by the manifest builder |

---

## 9. Known limitations

1. **Not live.** The Slack app does not exist yet. Creating it needs a human
   OAuth session. §10 is the whole remaining path.
2. **Slack is staged but disabled.** Enabling Slack before its tokens exist is
   not harmless: the gateway treats a missing `SLACK_BOT_TOKEN` as a
   non-retryable startup conflict and exits, which also stops the Clay scheduled
   work NORTH runs. This was hit for real during the build and the gateway was
   restored within a minute. `bin/clay-north-gateway-sync` now detects the tokens
   and only flips `enabled` once both are present, so the failure cannot repeat.
3. **`SLACK_ALLOWED_USERS` has to live in `.env`.** Slack is a built-in platform,
   so its per-user allowlist is only read from the environment, never from
   `config.yaml`. The sync script prints the exact line and never writes `.env`
   itself. The same applies to `SLACK_ALLOW_BOTS=none`, because
   `hermes config set` coerces the literal string `none` to YAML null.
4. **The ledger records what NORTH tells it.** `clay-ops work delegate` is how
   specialists get recorded; NORTH calling it is behavioral, driven by the
   contract in its role file, not enforced by the runtime.
5. **`#clay-north` does not exist.** Deliberate. Creating a channel in the live
   workspace is Ryan's decision.
6. **No Slack-side approval buttons.** An approval comes back as a NEEDS YOUR
   DECISION message naming the approver. Ryan answers in the thread. Block Kit
   approval buttons exist in the gateway and are not wired to the Clay
   authorization layer yet.

---

## 10. The remaining step

Everything below happens once, in a browser, as Ryan.

1. Open `https://api.slack.com/apps` and click **Create New App**.
2. Choose **From a manifest**.
3. Pick the **clayhc** workspace.
4. Paste the contents of `clay-ops/integrations/slack/north-app-manifest.json`,
   click **Next**, then **Create**.
5. **Basic Information → App-Level Tokens → Generate Token and Scopes.** Name it
   `north-socket`, add the scope **`connections:write`**, click **Generate**, and
   copy the `xapp-…` value. That is `SLACK_APP_TOKEN`. Socket Mode does not work
   without it.
6. **Install App → Install to Workspace → Allow.** Copy the **Bot User OAuth
   Token**, the `xoxb-…` value. That is `SLACK_BOT_TOKEN`.
7. Put both into `~/.hermes/profiles/north/.env`, along with the two lines the
   sync script prints:

   ```
   SLACK_BOT_TOKEN=xoxb-…
   SLACK_APP_TOKEN=xapp-…
   SLACK_ALLOWED_USERS=U0BH7234V9R,U0BJ6DUR2RF,U0BHA0L3C85,U0BHB9CDL22
   SLACK_ALLOW_BOTS=none
   ```

8. Turn it on:

   ```bash
   cd ~/ClayHQ-Automation/clay-ops
   bin/clay-north-gateway-sync        # detects the tokens, enables Slack
   hermes -p north gateway restart
   ```

9. In Slack, invite NORTH where it should work:

   ```
   /invite @NORTH        in #clay-studios
   /invite @NORTH        in #joinclay-mvp-landing-page
   ```

   If you want the dedicated channel, create `#clay-north`, invite NORTH, copy
   the channel ID from the channel's link, paste it into
   `config/team-access.json`, set that row's `enabled` to `true`, and re-run
   `bin/clay-north-gateway-sync`.

10. Check it. DM NORTH and ask for status. Then have Alex mention NORTH in
    `#clay-studios`. Then confirm someone outside the four gets no response.

### Changing access later

Edit `config/team-access.json`, then:

```bash
bin/clay-north-gateway-sync
hermes -p north gateway restart
```

Adding a person needs their Slack user ID added to `people`, and the
`SLACK_ALLOWED_USERS` line updated in `.env`, which the sync script prints.

---

## 11. Security notes

- No credential was created, entered, or read on anyone's behalf. The two Slack
  tokens do not exist yet and must be generated by Ryan.
- No `.env` file was written. The sync script prints the lines and refuses to
  write them.
- No public inbound port was opened, and no tunnel was started. The listener list
  on the Mac mini is byte-identical before and after.
- No Slack message was sent, no channel was created, and no Slack app was
  installed.
- The Slack app manifest carries no engine vocabulary. All 50 generated slash
  commands were stripped, along with the `commands` scope that only existed to
  serve them, because they are named after internals (`/hermes`, `/model`,
  `/compress`) and none of that belongs in the Clay workspace. A test asserts the
  manifest contains none of those words.
- The NORTH profile config was backed up before every change, to
  `~/.hermes/profiles/north/config.yaml.pre-team-access.<timestamp>`. The role
  file was backed up the same way.
