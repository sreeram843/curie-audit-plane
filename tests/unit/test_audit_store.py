import sqlite3

import pytest

from curie_audit_plane.models.enums import TransactionStatus
from curie_audit_plane.store.audit import AuditStore
from tests.helpers import make_event


def test_append_only_list_is_ordered(tmp_path):
    store = AuditStore(tmp_path / "audit.sqlite")
    store.create_transaction("tx-1", "purpose", "Patient/TEST-00001")
    first = make_event(event_id="e0", transaction_id="tx-1", sequence_number=0)
    second = make_event(event_id="e1", transaction_id="tx-1", sequence_number=1)
    store.append_event(first)
    store.append_event(second)
    events = store.list_events("tx-1")
    assert [event.event_id for event in events] == ["e0", "e1"]
    store.close()


def test_missing_transaction_raises(tmp_path):
    store = AuditStore(tmp_path / "audit.sqlite")
    with pytest.raises(KeyError):
        store.get_transaction("missing")
    store.close()


def test_status_update(tmp_path):
    store = AuditStore(tmp_path / "audit.sqlite")
    store.create_transaction("tx-1", "purpose", "Patient/TEST-00001")
    store.set_status("tx-1", TransactionStatus.RUNNING)
    row = store.get_transaction("tx-1")
    assert row["status"] == "RUNNING"
    store.close()


def test_audit_store_close_releases_connection(tmp_path):
    path = tmp_path / "audit.sqlite"
    store = AuditStore(path)
    store.create_transaction("tx-1", "purpose", "Patient/TEST-00001")
    store.append_event(make_event(transaction_id="tx-1"))
    store.close()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    finally:
        conn.close()
    assert count == 1
    with pytest.raises(sqlite3.ProgrammingError):
        store.list_events("tx-1")


def test_audit_store_context_manager_closes(tmp_path):
    path = tmp_path / "audit.sqlite"
    with AuditStore(path) as store:
        store.create_transaction("tx-1", "purpose", "Patient/TEST-00001")
    reopened = sqlite3.connect(path)
    try:
        assert reopened.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
    finally:
        reopened.close()
