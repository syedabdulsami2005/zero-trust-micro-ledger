"""Tests for the ledger append engine."""

import pytest

from backend.core.ledger_engine import LedgerEngine, LedgerFrozenError
from backend.core.normalizer import reset_event_counter
from backend.core.storage import Storage
from backend.core.hasher import canonical_serialize, compute_hash


@pytest.fixture(autouse=True)
def _reset_counter():
    reset_event_counter(0)
    yield
    reset_event_counter(0)


@pytest.fixture
def engine(tmp_path):
    """Create an initialised LedgerEngine with a temp data directory."""
    storage = Storage(tmp_path / "data")
    eng = LedgerEngine(storage)
    eng.initialize()
    return eng


def _raw_event(**overrides) -> dict:
    """Return a minimal raw event for testing."""
    base = {
        "event_type": "file_modified",
        "source_type": "config_file",
        "source_path": "/etc/device.conf",
    }
    base.update(overrides)
    return base


# ── Initialisation ─────────────────────────────────────────────────────

class TestInitialize:
    def test_creates_genesis_block(self, tmp_path):
        storage = Storage(tmp_path / "data")
        engine = LedgerEngine(storage)
        genesis = engine.initialize()
        assert genesis["block_index"] == 0
        assert genesis["event_type"] == "genesis"

    def test_chain_length_is_one_after_init(self, engine):
        assert engine.get_chain_length() == 1

    def test_last_block_is_genesis(self, engine):
        last = engine.get_last_block()
        assert last is not None
        assert last["block_index"] == 0

    def test_reinitialize_loads_existing(self, tmp_path):
        storage = Storage(tmp_path / "data")
        eng1 = LedgerEngine(storage)
        eng1.initialize()
        eng1.append_event(_raw_event())
        eng1.append_event(_raw_event())

        # Simulate restart
        eng2 = LedgerEngine(storage)
        last = eng2.initialize()
        assert eng2.get_chain_length() == 3
        assert last["block_index"] == 2


# ── Append ─────────────────────────────────────────────────────────────

class TestAppendEvent:
    def test_increments_block_index(self, engine):
        b1 = engine.append_event(_raw_event())
        assert b1["block_index"] == 1
        b2 = engine.append_event(_raw_event())
        assert b2["block_index"] == 2

    def test_chain_linking(self, engine):
        genesis = engine.get_last_block()
        b1 = engine.append_event(_raw_event())
        assert b1["previous_hash"] == genesis["current_hash"]
        b2 = engine.append_event(_raw_event())
        assert b2["previous_hash"] == b1["current_hash"]

    def test_hash_correctness(self, engine):
        block = engine.append_event(_raw_event())
        serialized = canonical_serialize(block)
        expected = compute_hash(block["previous_hash"], serialized)
        assert block["current_hash"] == expected

    def test_chain_length_increments(self, engine):
        assert engine.get_chain_length() == 1
        engine.append_event(_raw_event())
        assert engine.get_chain_length() == 2
        engine.append_event(_raw_event())
        assert engine.get_chain_length() == 3

    def test_last_block_updated(self, engine):
        b = engine.append_event(_raw_event())
        assert engine.get_last_block() == b

    def test_raises_if_not_initialized(self, tmp_path):
        storage = Storage(tmp_path / "data2")
        eng = LedgerEngine(storage)
        with pytest.raises(RuntimeError, match="not initialised"):
            eng.append_event(_raw_event())


# ── Freeze / Unfreeze ──────────────────────────────────────────────────

class TestFreeze:
    def test_freeze_blocks_append(self, engine):
        engine.freeze()
        assert engine.is_frozen()
        with pytest.raises(LedgerFrozenError):
            engine.append_event(_raw_event())

    def test_unfreeze_resumes_append(self, engine):
        engine.freeze()
        engine.unfreeze()
        assert not engine.is_frozen()
        block = engine.append_event(_raw_event())
        assert block["block_index"] == 1

    def test_freeze_persisted_across_restart(self, tmp_path):
        storage = Storage(tmp_path / "data")
        eng1 = LedgerEngine(storage)
        eng1.initialize()
        eng1.freeze()

        eng2 = LedgerEngine(storage)
        eng2.initialize()
        assert eng2.is_frozen()

    def test_multiple_events_after_unfreeze(self, engine):
        engine.freeze()
        engine.unfreeze()
        b1 = engine.append_event(_raw_event())
        b2 = engine.append_event(_raw_event())
        assert b2["previous_hash"] == b1["current_hash"]


# ── Full chain integrity ──────────────────────────────────────────────

class TestChainIntegrity:
    def test_five_block_chain_links_correctly(self, engine):
        """Build a 5-block chain and verify every link."""
        blocks = [engine.get_last_block()]  # genesis
        for _ in range(4):
            blocks.append(engine.append_event(_raw_event()))

        for i in range(1, len(blocks)):
            assert blocks[i]["previous_hash"] == blocks[i - 1]["current_hash"]
            assert blocks[i]["block_index"] == i

    def test_hashes_are_all_unique(self, engine):
        blocks = [engine.get_last_block()]
        for _ in range(4):
            blocks.append(engine.append_event(_raw_event()))
        hashes = [b["current_hash"] for b in blocks]
        assert len(set(hashes)) == len(hashes)
