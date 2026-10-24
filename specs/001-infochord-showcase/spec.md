# Feature Specification: InfoChord Portfolio Showcase

**Feature Branch**: `001-infochord-showcase`
**Created**: 2026-10-23
**Status**: Implementation in progress ? runtime acceptance remains evidence-gated
**Input**: Prepare the existing InfoChord prototype as a credible technical project and reproducible demo.

## User Scenarios & Testing

### Reviewer understands the project (Priority: P1)

A hiring reviewer can understand the system's purpose, major components, data flow, and current maturity from the repository landing page without relying on unsupported reliability claims.

**Why this priority**: The repository is intended to be shown as a project; clarity and technical credibility are its primary outcomes.

**Independent Test**: Give the README to a technical reviewer and confirm they can describe the client, embedding service, distributed nodes, and the distinction between implemented behavior and verified guarantees.

**Acceptance Scenarios**:
1. **Given** the repository root, **When** a reviewer reads the README, **Then** it identifies InfoChord as a prototype for distributed semantic document search and explains its main components and limitations.
2. **Given** a claim about replication, failover, or consistency, **When** the docs describe it, **Then** the claim is either tied to evidence/tests or explicitly marked unverified.

### Reviewer can attempt a local demo (Priority: P1)

A developer with Docker and an OpenAI-compatible embedding endpoint can build the image, start the Compose containers, manually start several nodes and the Streamlit UI, and understand any remaining runtime limitations.

**Why this priority**: A reproducible demo makes the architecture tangible and prevents the showcase from being documentation-only.

**Independent Test**: Follow the documented commands from a clean checkout; record successful checks and blockers without assuming Docker availability.

**Acceptance Scenarios**:
1. **Given** Docker is available, **When** a developer follows the documented setup, **Then** the image, containers, server entrypoint, UI entrypoint, and required embedding configuration are unambiguous.
2. **Given** Docker or the embedding endpoint is unavailable, **When** setup is attempted, **Then** the README describes the dependency and does not claim the demo has been runtime-validated.

### User safely operates document CRUD (Priority: P1)

A user can navigate the UI without an accidental document deletion and must explicitly confirm before deletion is sent to the backend.

**Why this priority**: A public demo must not mutate data merely because a page was rendered or selected.

**Independent Test**: Load the delete page with a document name but do not confirm; verify no delete request is made. Confirm the action and verify the delete function is called once.

**Acceptance Scenarios**:
1. **Given** the delete page is opened or rerun, **When** the user has not confirmed deletion, **Then** no backend delete call occurs.
2. **Given** a non-empty document name and an explicit confirmation, **When** the user activates delete, **Then** the request is made once and the result is displayed.
3. **Given** an empty document name, **When** delete is attempted, **Then** the UI warns the user and does not call the backend.

### Project configuration remains safe to share (Priority: P2)

A contributor can distinguish safe defaults from machine-local settings and can see which generated/local artifacts should not be committed.

**Independent Test**: Inspect tracked configuration examples and ignore rules; confirm no credentials or machine-specific paths are published.

## Requirements

### Functional Requirements

- **FR-001**: The README MUST explain the prototype's purpose, high-level architecture, data flow, and implemented client capabilities.
- **FR-002**: The README MUST provide setup/start instructions consistent with the current Docker Compose mounts, image, server script, UI script, and embedding configuration.
- **FR-003**: The documentation MUST separate observed source behavior from tests or runtime behavior that has not been verified.
- **FR-004**: Selecting or rendering the delete page MUST NOT call the backend. Deletion MUST require a non-empty name and an explicit confirmation action.
- **FR-005**: The demo guidance MUST use disposable sample documents and caution against uploading private data.
- **FR-006**: Spec Kit project rules and the showcase specification MUST be tracked while machine-local Spec Kit state remains ignored.
- **FR-007**: Public-facing configuration guidance MUST use safe placeholders and MUST NOT disclose local credentials or machine paths.

### Key Entities

- **Document**: A named text/file record sent through client CRUD operations, embedded, stored by the distributed service, and returned for search/download.
- **Node**: A server process participating in the Chord-oriented topology and serving storage/search endpoints.
- **Embedding Provider**: An external OpenAI-compatible endpoint used to convert text into vectors; required for embedding-dependent operations.
- **Showcase Evidence**: A test result, source reference, or documented observation supporting a project capability or limitation.

## Success Criteria

- **SC-001**: A technical reader can identify the UI, API, embedding, node, and storage roles from the README in under five minutes.
- **SC-002**: A developer can find the exact build/start commands and required embedding settings without searching source files.
- **SC-003**: Automated or manual verification demonstrates that opening the delete page alone never triggers deletion.
- **SC-004**: All reliability claims in the showcase are qualified by evidence; unverified behavior is labeled as such.
- **SC-005**: Spec Kit setup checks pass and tracked documentation contains no machine-local Spec Kit pointer state.

## Assumptions

- The repository is a prototype, not a production-ready or security-audited service.
- The Streamlit UI may remain Spanish while project-level showcase documentation is English.
- Docker Compose starts three nodes and the UI automatically; only the UI is published on loopback.
- Runtime verification depends on Docker daemon availability and a reachable embedding provider.

## Out of Scope

- Changing document identity, replacing Chord or SQLite, or automatically migrating legacy databases.
- Claiming availability, consistency, throughput, or fault-tolerance guarantees without a dedicated test effort.
- Replacing the UI or embedding provider.
- Publishing credentials, sample personal documents, or a deployed public service.

## Approved follow-up acceptance (2026-10-23)

- Application serialization is versioned, allow-listed JSON; no pickle/jsonpickle decoding remains in runtime paths.
- TCP framing supports partial reads and enforces message/deadline limits. HTTP protocol changes are documented.
- New v1 volumes isolate demo data; legacy databases are refused without modification. No mixed-version rollout.
- The same Docker gate runs locally and in CI for CRUD/search, owner redirect, persistence, one-node failure/recovery and provider outage.
- Client failures are bounded and visible; ambiguous writes are not retried automatically.
- Real-provider evidence and current captures are required before claiming the presentation is verified.
