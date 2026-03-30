"""Unit tests for TapeAnchor, TapeView, AnchorStrategy data models."""

import pytest
from simu_emperor.memory.models import (
    TapeAnchor,
    TapeView,
    AnchorStrategy,
    TapeMetadataEntry,
)


class TestTapeAnchor:
    def test_create_anchor(self):
        anchor = TapeAnchor(
            anchor_id="anchor:sess1:0",
            name="handoff/conversation_end",
            tape_position=0,
            state={"summary": "test summary", "source_entry_ids": [], "tick_range": [1, 2]},
            created_at="2026-01-01T00:00:00Z",
            created_tick=1,
        )
        assert anchor.anchor_id == "anchor:sess1:0"
        assert anchor.state["summary"] == "test summary"

    def test_anchor_serialization_roundtrip(self):
        anchor = TapeAnchor(
            anchor_id="anchor:sess1:0",
            name="handoff/compaction",
            tape_position=10,
            state={"summary": "s", "source_entry_ids": ["e1"], "tick_range": [1, 3]},
            created_at="2026-01-01T00:00:00Z",
            created_tick=1,
        )
        d = anchor.to_dict()
        restored = TapeAnchor.from_dict(d)
        assert restored.anchor_id == anchor.anchor_id
        assert restored.state == anchor.state


class TestTapeView:
    def test_create_view(self):
        view = TapeView(
            view_id="view:anchor:sess1:0",
            session_id="sess1",
            agent_id="agent1",
            anchor_start_id=None,
            anchor_end_id="anchor:sess1:0",
            tape_position_start=0,
            tape_position_end=9,
            events=[{"event_id": "e1"}],
            anchor_state={"summary": "test"},
            tick_start=1,
            tick_end=2,
            event_count=1,
        )
        assert view.view_id == "view:anchor:sess1:0"
        assert view.frozen  # TapeView is frozen

    def test_view_to_text_uses_anchor_state(self):
        view = TapeView(
            view_id="v1",
            session_id="s1",
            agent_id="a1",
            anchor_start_id=None,
            anchor_end_id="a1",
            tape_position_start=0,
            tape_position_end=0,
            events=[{"payload": {"message": "hello"}}],
            anchor_state={"summary": "test summary"},
            tick_start=None,
            tick_end=None,
            event_count=1,
        )
        text = view.to_text()
        assert "test summary" in text
        assert "hello" in text


class TestTapeMetadataEntryNew:
    def test_has_anchor_index_no_segment_index(self):
        entry = TapeMetadataEntry(
            session_id="s1",
            title="test",
            created_tick=1,
            created_time="2026-01-01T00:00:00Z",
            last_updated_tick=1,
            last_updated_time="2026-01-01T00:00:00Z",
        )
        assert hasattr(entry, "anchor_index")
        assert entry.anchor_index == []
        assert not hasattr(entry, "segment_index") or entry.segment_index == []

    def test_to_dict_contains_anchor_index(self):
        entry = TapeMetadataEntry(
            session_id="s1",
            title="test",
            created_tick=1,
            created_time="2026-01-01T00:00:00Z",
            last_updated_tick=1,
            last_updated_time="2026-01-01T00:00:00Z",
            anchor_index=[{"anchor_id": "a1"}],
        )
        d = entry.to_dict()
        assert "anchor_index" in d
        assert d["anchor_index"] == [{"anchor_id": "a1"}]
