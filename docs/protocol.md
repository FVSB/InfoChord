# InfoChord protocol and storage v1

This is a local-demo protocol, not an authenticated public API or a security certification.

## Format

Every serialized value is UTF-8 JSON: `{"version":1,"payload":...}`. Built-in scalars, string-keyed dictionaries and lists are supported. Tagged values use exactly `{"$":"Type","data":...}`.

Allowed tags: Bytes (validated base64), Time (ISO timestamp), Tuple, Set, Vector (finite numeric elements), Crud (known enum member), and the exact Node, Record, Document, EmbeddingDocument, Result, Heap, Query and Packet field sets in `infochord_protocol/codec.py`.

Unknown tags, fields and protocol versions are rejected. Constructors/callbacks/module names are never chosen from input. Query scoring is fixed locally after decoding; no functions or locks are serialized. Vector dimensions and chunk counts are checked on document decoding.

Maximum encoded message: **10 MiB**. Maximum decoded contract nesting: **40**. TCP messages have a four-byte unsigned network-order length followed by exactly that many bytes, with a **20-second frame read deadline**. UDP discovery uses one bounded JSON datagram.

## HTTP

- Existing CRUD and node-to-node POST routes accept the versioned envelope as the raw `application/json` body, not multipart file uploads.
- `/upload` and `/update` payloads are `(title, text)` tuples; `/delete_file` takes the title string. Empty document title/text is rejected.
- Existing normal CRUD/progress/query response dictionaries remain JSON. Internal query handles and document retrieval use versioned envelopes.
- `/get_document_by_name?name=...` returns the complete text envelope; the old package/resume transfer format is removed. Deleted documents return 404.
- `/health/live` reports the running HTTP process. `/health/ready` checks local SQL access and current cluster/database stability; embedding health is a separate preflight.
- Client requests have connect/read timeouts; search retries three times, redirects are capped at eight, and document progress has a 120-second polling deadline. Writes are not automatically retried after ambiguous failures.

## Persistence and compatibility

SQLite stores UTF-8 JSON envelope bytes in the existing document blob column. `PRAGMA user_version=1` identifies the new format. A nonempty unversioned database, or another format version, is rejected before any application tables are changed.

Old databases are preserved, not migrated or decoded. New Compose volumes are namespaced by project and suffixed `v1`. Client and all nodes must be upgraded/restarted together. Rollback uses the previous code AND separate previous storage.

The existing title-based document identity is retained. This protocol migration does not establish collision resistance, global consistency or distributed durability guarantees.
