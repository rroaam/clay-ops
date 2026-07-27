# Architecture

| Truth class | Owner | Clay Ops relationship |
|---|---|---|
| Product, brand/design, healthcare/claims, decisions, deployment policy | `clayhc-clay-engine` | Pinned read-only references only |
| Tasks, runs, events, approvals, artifacts, snapshots | `clay-ops` | Operational owner |
| Clay HQ dashboard | `clay-engine/dashboard` | Replaceable projection and command surface; never canon |

Clay Ops resolves explicit sibling roots from `config/canon-registry.json`; contracts contain no user-specific absolute paths. Runtime state is SQLite plus immutable artifacts below `runtime/`. Browser code must use a server-side projection/API and never read SQLite or hold a Hermes bearer token.

The Hermes adapter is provider-neutral and allowlists only capabilities, runs, run events, approvals, stop, and read-only sessions. Capability detection precedes feature use. The API server remains disabled until supervised approval.
