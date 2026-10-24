# Demo walkthrough and evidence checklist

Use a fresh checkout, Docker Desktop with Compose >=2.24.4, and a real OpenAI-compatible embedding model. Never use personal documents.

## Present in two minutes

1. Run `./scripts/start-demo.ps1`; explain that three Chord-inspired nodes each store a local SQLite database.
2. Open http://localhost:8501 and insert `orchard.txt` with: `Oranges are citrus fruit grown in orchards.`
3. Insert `systems.txt` with: `Distributed systems route documents between nodes and replicate local storage.`
4. Search `fruit grown on trees` with extension `txt`. Explain the ranking as observed, not as a benchmark.
5. Retrieve the selected document, update its text, and repeat the query.
6. Open the deletion page: rendering alone must not delete anything. Confirm and explicitly click to delete.
7. Stop with `./scripts/stop-demo.ps1`. Volumes remain available for the next start.

## Evidence rules

- Capture a current UI screenshot and short GIF only after the REAL provider and the complete walkthrough pass.
- Keep screenshots free of credentials, host-specific information and private content.
- Label the deterministic fixture as a test double, never as semantic-search evidence.
- A screenshot proves only that observed UI state. Node-failure behavior needs integration-test output.
- Do not add performance, availability, consistency or recovery guarantees based on a single demo.

## Recovery and troubleshooting

- **Provider check fails:** start the configured model and verify `.env`; no cluster is started by the startup script when preflight fails.
- **Node unhealthy:** inspect `docker compose ps` and `docker compose logs --tail 100 node1 node2 node3`. Readiness does not depend on provider availability.
- **Write timed out:** its outcome may be unknown. Retrieve/search the document before retrying; the client does not retry writes automatically.
- **Legacy database:** use the new v1 volumes. Never mount an old database into this version or try to deserialize its blobs.
- **Rollback:** stop this version, check out the previous commit, and use its original storage separately. No rolling/mixed-version operation is supported.
- **Test diagnostics:** `python scripts/check-demo.py` prints its unique project name and retains its volumes. It stops only that project, never other Docker projects.

No volume removal is part of normal start, stop, test, or rollback. Inspect and explicitly approve any later cleanup separately.
