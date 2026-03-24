# AAC Protocol Testing Status

## Current state

### What we have

- **Unit tests** (`tests/unit/`): models, **platform escrow ledger** (`test_token.py` — name kept for history; covers `EscrowLedger`), **platform dispute flow** (`test_arbitration.py`).
- **Integration / e2e** (`tests/integration/`, `tests/e2e/`): agent flow and full scenarios against in-memory SQLite.
- **Infrastructure**: pytest + pytest-asyncio.

### Honest limits

- **Centralized stack**: No blockchain, multi-node registry, or Merkle/VRF arbitration — those paths were removed from the codebase.
- **No production hardening**: No load tests, security fuzzing, or real PSP/fiat integration tests.
- **Python**: `setup.py` requires **Python 3.10+**; run `pip install -e ".[dev]"` from the repo root so imports resolve (package layout uses the `aac_protocol` namespace as configured in your environment).
