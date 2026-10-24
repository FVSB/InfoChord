# Validation evidence — 2026-10-24

**Status: implementation candidate; not cleared for merge or a verified live presentation.**

## Observed locally

- The dependency lock was generated with transitive hashes and installed with `--require-hashes` in an isolated temporary Python 3.11 environment.
- The final local suite passed: **29 tests in 85.457 seconds**, covering contracts, real socket framing, HTTP routes/validation, SQLite persistence and legacy rejection, client bounds, logging and real Streamlit rendering. Backends are mocked in UI tests; this is not a live cluster demo.
- Python syntax compilation passed for the application, protocol, scripts and tests.
- `docker compose -f docker-compose.yml -f compose.test.yml config --quiet` passed.
- `git diff --check` passed for implementation paths, excluding unrelated user edits.
- Existing user edits in Agent OS standards and Claude settings were not edited or included in the implementation.

The local verification interpreter is CPython 3.11.10 x64 on Windows. Managed interpreters and test dependencies were installed in temporary locations; no system Python/PATH settings were changed.

## Actual blockers, not test passes

- The isolated Docker gate `infochord-test-255859cef6` failed **before cluster startup**, during image construction, because the `dockerDesktopLinuxEngine` named pipe was unavailable. Diagnostics and stop commands also could not reach the engine. No volume deletion was attempted.
- Docker Desktop was launched only after no active Desktop/backend process was found. The engine still did not respond during a bounded readiness wait; no active daemon was restarted and no unrelated containers were stopped.
- The default real embedding endpoint at `127.0.0.1:1234` did not respond to a model-list request. A real-provider walkthrough, current screenshots and GIF therefore remain pending.
- CI and distributed scenarios must not be described as passing until their actual run results are recorded.

## Fixes discovered through verification

- The newly resolved PyArrow runtime requires NumPy 2; a real Streamlit test exposed the ABI mismatch that backend mocks did not. The direct requirement and hashed lock were updated together.
- Updated document embeddings now retain the matching text chunks.
- Query tracking now actually removes completed identifiers.
- Real-socket tests cover both node references and server handlers, including responses larger than the previous 1024-byte read limit.
- HTTP contract tests exercise real route registration, health checks and validation without starting topology threads.

## Acceptance still required

1. Keep the passing 29-test local result separate from still-pending integration evidence.
2. Build the image and pass the complete isolated multi-node gate (including restart, one-node failure/recovery and provider outage).
3. Verify the real-provider demo from a clean checkout and capture the current UI.
4. Review the final diff/CI, update the existing draft PR, and only then decide separately about merge readiness. This task does not merge main.

Use `python scripts/check-demo.py` for the same integration gate used in CI. The fixture is deterministic test data, not evidence of real-model semantic quality or general distributed guarantees.
