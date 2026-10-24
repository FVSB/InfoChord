# Protocol Codes

All inter-node messages use integer constants from `helper/protocol_codes.py`.

- Define ALL new codes in `protocol_codes.py` only — never inline in other files
- Each code must have a unique integer — check the file before adding
- Import with `from helper.protocol_codes import *`

Current range: 1–31. Next code goes at the end sequentially.
