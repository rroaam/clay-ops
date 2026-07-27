# Operating invariants

1. Canon stays in the canonical repository; Clay Ops stores pointers and hashes only.
2. Dashboard state is never authoritative.
3. Events, approval requests, and approval decisions are append-only; each request can receive exactly one decision.
4. Completed result packets are immutable.
5. Every artifact has a SHA-256 hash and confined path.
6. Every review records input hash, target surface, provenance, acceptance criteria, and pinned canon snapshots.
7. Obvious unsupported health claims fail. Unresolved healthcare/outcome claims require human review and never receive clinical approval from Ryan alone.
8. Review approval never edits, sends, publishes, deploys, or changes canon.
9. Hermes activity is structured only when launched through the Runs API; existing TUI sessions are manual/unstructured.
10. Offline/degraded integrations are reported truthfully, never fabricated.
