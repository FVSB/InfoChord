# Implementation Plan: Reproducible and Safe Local Showcase

## Approved decisions

- Local demo only; no authentication/public deployment or merge to main.
- Replace unsafe serializers across client, node protocol, query transfer and SQLite.
- Use new isolated demo storage. Preserve old databases without loading or migrating them.
- Preserve unrelated local Agent OS and Claude configuration edits.

## Implementation

1. Pin the Python 3.11 Debian image by digest, hash-lock imported runtime dependencies, cache tiktoken during build, and remove unused NLP libraries.
2. Start three nodes and UI automatically in Compose; optionally start seven. Publish only loopback UI. Separate process/cluster readiness from provider preflight.
3. Introduce explicit JSON v1 DTOs, bounded framing, numeric-vector/schema validation, safe fixed query scoring and SQLite format detection. Upgrade all participants together.
4. Bound discovery, HTTP, redirections, search retries and progress polling. Never retry ambiguous writes automatically. Surface processing/provider failures in UI.
5. Test contracts, invalid payloads, partial TCP reads, legacy rejection, storage persistence, client failure bounds and deletion confirmation. Run the same isolated Docker fault scenarios locally and in CI.
6. Update README, walkthrough, protocol/rollback documentation and evidence. Capture real UI only after the actual provider walkthrough passes.

## Verification and delivery

`python scripts/check-demo.py` is the build/unit/three-node integration gate. It covers restart, stopped-node CRUD/search and reincorporation with bounded waits. Failure remains failure: do not weaken assertions to claim completion.

Record actual outcomes in `docs/validation.md`. Keep runtime evidence distinct from source-level behavior and deterministic fixtures. No main merge, public deployment, database cleanup or undocumented reliability claims.
