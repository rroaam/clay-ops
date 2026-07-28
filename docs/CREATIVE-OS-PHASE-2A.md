# Creative OS Phase 2A: Asset, Gallery, and Image Foundation

## Boundary and architecture

Phase 2A remains a local-only Clay Ops capability. SQLite is authoritative for creative projects, generation requests, creative assets, runs, append-only events, and append-only approvals. The dashboard and all HTTP read endpoints are projections. Clay Ops does not write product canon, dashboard code, credentials, member data, or external-service configuration.

The data chain is explicit:

`creative project → generation request → run → approval → provider attempt → creative asset/artifact`

Assets retain project/request/run links, optional parent-asset and variant indexes, favorite/tags, immutable content hash, dimensions, provenance, and evidence. Project-scoped queries filter in SQLite and never infer ownership from client input.

## Provider contract and lifecycle

`ImageProvider` is provider-neutral: each registered provider exposes an ID, capability discovery, and `generate(request)`. Capabilities report availability, models, aspect ratios, reference support, and maximum variants. The default registry contains only the unavailable provider; it performs no call and reports `unavailable`.

Submission records a project, request, run, capability result, and event before any attempt. Unsupported or unavailable requests remain `blocked` / `not_attempted`, with no fabricated output. Available requests become `awaiting_approval`. Provider execution requires the exact approval ID and scope to have one append-only `approved` decision. Replays are rejected. Provider outcomes remain `partial`, `completed`, `failed`, or `cancelled`; errors are normalized and redacted. Provider bytes are signature-checked before confined artifact storage and become request-linked generated variants.

No provider is configured by Phase 2A and no external execution occurs by default.

## Safe local import

`POST /api/imports/images` accepts base64-encoded request bytes—not a client file path—and uses the same exact command boundary as existing commands: loopback `Host`, exact `Origin: http://127.0.0.1:3001`, marker `X-Clay-HQ-Server: 1`, and JSON content type.

Imports:

- allow only PNG, JPEG, WebP, and GIF MIME types;
- verify declared MIME against file signatures;
- enforce a configurable byte cap;
- reject path components and normalize safe display filenames;
- write atomically beneath `runtime/artifacts` using confined, no-symlink paths;
- derive dimensions with standard-library binary parsing where supported;
- record SHA-256, byte count, signature evidence, and `imported/request_bytes` provenance.

## API and projections

Command routes create projects, submit generation requests, import local images, and edit favorite/tags. Read routes expose the projection, project lists/details, project-scoped assets, and generation requests. They remain loopback-host-only and emit no CORS permission.

The projection adds `projects`, `assets`, `generation_requests`, and `providers`, plus exact counts and image health. `connected_verified` is used only after provider-backed attempt evidence; capability without an attempt is `available_not_verified`; the default is `unavailable`.

## Roadmap

`registries/creative-workflows.json` is the roadmap registry. Image is `functional` in Phase 2A. Design, landing, email, campaign, social, presentation, moodboard, and video are `planned`; those labels do not claim implementations or external connectivity.
