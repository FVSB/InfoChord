# Tasks: InfoChord Portfolio Showcase

## Existing baseline
- [x] Initialize Spec Kit, constitution and showcase artifacts.
- [x] Publish the initial showcase branch and draft PR #1 (historical action, not re-verified by this implementation).
- [x] Preserve unrelated local standards/configuration edits.

## Implementation
- [x] Automatic three-node Compose demo; optional seven-node profile; loopback-only UI.
- [x] Shared JSON v1 contracts, framed TCP and replacement of application pickle/jsonpickle use.
- [x] New SQLite JSON format with refusal of legacy databases; isolated named volumes.
- [x] Bounded client behavior, visible UI errors and provider failure tracking.
- [x] Regression tests for text-chunk updates and query-tracking cleanup.
- [x] Unit tests, deterministic provider fixture and Docker integration/failure orchestrator.
- [x] CI workflow and safe diagnostic handling.
- [x] Dependency lock, base-image digest and build-time tokenizer cache.
- [x] Startup/shutdown scripts, protocol documentation and presentation walkthrough.

## Acceptance evidence — do not check until observed
- [x] Complete hashed-environment local suite: 29 tests passed.
- [x] Validate base + test Compose configuration and implementation whitespace checks.
- [ ] Complete image build and containerized test run.
- [ ] Passing multi-node CRUD/search/redirect gate.
- [ ] Passing restart, node failure/recovery and provider outage scenarios.
- [ ] Real-provider demo verified from a clean checkout.
- [ ] Current screenshot and GIF captured from the verified walkthrough.
- [ ] Final diff review, relevant commits and draft PR update.

See `docs/validation.md` for concrete results and blockers. No merge to main is authorized by this task.
