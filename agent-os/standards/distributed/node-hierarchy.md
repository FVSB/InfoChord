# Node Hierarchy

Chord nodes use layered inheritance — each layer adds one responsibility:

```
ChordNode               # Chord protocol (routing, fingers, stabilize)
  └ Leader              # Leader election
    └ StoreNode         # Document storage + Flask HTTP API
      └ SyncStoreNode   # Data resync on node join/leave
        └ DistributedDataBase  # DB stability + CUD gating
```

- Each layer handles only its own option codes in `handle_request()`
- Always call `super().handle_request()` at the end for unhandled codes
- Use `DistributedDataBase` as the concrete node class in production
