"""Tests for PageAggregate.set_extension — event-backed extension mutation.

Regression suite for the "lost-on-reload" bug where mutating PageRecord.extensions
directly after first save did NOT persist across replay (0.7.0 behaviour).
All four tests below must FAIL against the 0.7.0 implementation and PASS after 0.7.1.
"""

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel

from pdomain_ops.page_aggregate import PageAggregate, PagesApplication
from pdomain_ops.pages import PageRecord


class _LabelerState(BaseModel):
    """Tiny extension model used as test fixture."""

    cursor_word_id: str = ""
    zoom: float = 1.0
    flags: list[str] = []


def _sqlite_env(tmp_path: Path) -> dict[str, str]:
    return {
        "PERSISTENCE_MODULE": "eventsourcing.sqlite",
        "SQLITE_DBNAME": str(tmp_path / "events.db"),
    }


# ---------------------------------------------------------------------------
# 1. Reproduction / regression test
# ---------------------------------------------------------------------------


def test_set_extension_persists_across_replay(tmp_path: Path) -> None:
    """Extension set via PageAggregate.set_extension survives reload from sqlite.

    This is the key regression: on 0.7.0 code the update would be present in
    memory but lost on reload because the mutation was not captured as an event.
    """
    app = PagesApplication(env=_sqlite_env(tmp_path))
    pid = uuid4()

    # Create + initial save
    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=0))
    app.save(agg)

    # Reload and confirm extension absent initially
    reloaded: PageAggregate = app.repository.get(pid)
    assert reloaded.record.extensions == {}

    # Update extension via the event-backed command
    v1 = _LabelerState(cursor_word_id="w1", zoom=1.5, flags=["reviewed"])
    reloaded.set_extension("labeler", v1)
    app.save(reloaded)

    # Fresh reload from events -- extension must reflect the update
    reloaded2: PageAggregate = app.repository.get(pid)
    assert "labeler" in reloaded2.record.extensions
    stored = _LabelerState.model_validate(reloaded2.record.extensions["labeler"])
    assert stored.cursor_word_id == "w1"
    assert stored.zoom == pytest.approx(1.5)
    assert stored.flags == ["reviewed"]


def test_set_extension_update_persists_across_replay(tmp_path: Path) -> None:
    """A second set_extension call (update) also survives reload.

    Sequence: create -> set v1 -> save -> reload -> set v2 -> save -> reload
    Final reload must show v2.
    """
    app = PagesApplication(env=_sqlite_env(tmp_path))
    pid = uuid4()

    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=0))
    agg.set_extension("labeler", _LabelerState(cursor_word_id="w1"))
    app.save(agg)

    reloaded: PageAggregate = app.repository.get(pid)
    reloaded.set_extension("labeler", _LabelerState(cursor_word_id="w2", zoom=2.0))
    app.save(reloaded)

    final: PageAggregate = app.repository.get(pid)
    stored = _LabelerState.model_validate(final.record.extensions["labeler"])
    assert stored.cursor_word_id == "w2"
    assert stored.zoom == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# 2. Event-captured test
# ---------------------------------------------------------------------------


def test_set_extension_records_event_and_increments_version() -> None:
    """set_extension records an ExtensionSet event; aggregate version increments."""
    pid = uuid4()
    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=0))
    version_before = agg.version

    agg.set_extension("prep", _LabelerState(cursor_word_id="x"))

    assert agg.version == version_before + 1
    # The pending event should be an ExtensionSet (check by class name)
    pending = list(agg.pending_events)
    assert any(type(e).__name__ == "ExtensionSet" for e in pending)


# ---------------------------------------------------------------------------
# 3. By-reference safety test
# ---------------------------------------------------------------------------


def test_set_extension_deep_copy_isolates_from_caller() -> None:
    """Mutating the caller's model after set_extension must not affect the aggregate."""
    pid = uuid4()
    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=0))

    state = _LabelerState(cursor_word_id="original", flags=["a"])
    agg.set_extension("labeler", state)

    # Mutate caller's object after the call
    state.cursor_word_id = "mutated"
    state.flags.append("b")

    # Aggregate must reflect the value AT call time
    stored = _LabelerState.model_validate(agg.record.extensions["labeler"])
    assert stored.cursor_word_id == "original"
    assert stored.flags == ["a"]


# ---------------------------------------------------------------------------
# 4. Round-trip transcoding test
# ---------------------------------------------------------------------------


def test_set_extension_round_trips_through_transcoding(tmp_path: Path) -> None:
    """PageRecord with extension set via the command serializes and reloads cleanly."""
    app = PagesApplication(env=_sqlite_env(tmp_path))
    pid = uuid4()

    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=3))
    agg.set_extension(
        "prep",
        _LabelerState(cursor_word_id="p7", zoom=0.8, flags=["flag1", "flag2"]),
    )
    app.save(agg)

    reloaded: PageAggregate = app.repository.get(pid)
    assert reloaded.record.page_index == 3
    assert "prep" in reloaded.record.extensions
    state = _LabelerState.model_validate(reloaded.record.extensions["prep"])
    assert state.cursor_word_id == "p7"
    assert state.zoom == pytest.approx(0.8)
    assert state.flags == ["flag1", "flag2"]


# ---------------------------------------------------------------------------
# 5. Snapshotted reload consistency test
# ---------------------------------------------------------------------------


def test_set_extension_consistent_after_snapshot(tmp_path: Path) -> None:
    """Extension set via command is consistent when loaded from a snapshot.

    The snapshotting interval is set to 2, so after 2 events a snapshot is
    taken. We fire enough events to trigger snapshotting, then verify the
    extension value is correct on reload.
    """

    class SnappyApp(PagesApplication):
        snapshotting_intervals = {PageAggregate: 2}  # noqa: RUF012

    app = SnappyApp(env=_sqlite_env(tmp_path))
    pid = uuid4()

    agg = PageAggregate(record=PageRecord(page_id=pid, page_index=0))
    # version 1 = ImageIngested (from __init__)
    agg.set_extension("labeler", _LabelerState(cursor_word_id="snap_test", zoom=3.0))
    # version 2 = ExtensionSet -> snapshot taken
    app.save(agg)

    assert app.snapshots is not None
    snaps = list(app.snapshots.get(pid))
    assert len(snaps) >= 1

    reloaded: PageAggregate = app.repository.get(pid)
    stored = _LabelerState.model_validate(reloaded.record.extensions["labeler"])
    assert stored.cursor_word_id == "snap_test"
    assert stored.zoom == pytest.approx(3.0)
