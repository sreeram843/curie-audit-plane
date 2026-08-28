import json
import sqlite3
import threading
import weakref
from datetime import UTC, datetime
from pathlib import Path

from curie_audit_plane.models.enums import TransactionStatus
from curie_audit_plane.models.event import AuditEventRecord


class AuditStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._finalizer = weakref.finalize(self, sqlite3.Connection.close, self._conn)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY,
                purpose TEXT NOT NULL,
                subject_ref TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                ended_at TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                sequence_number INTEGER NOT NULL,
                event_json TEXT NOT NULL,
                UNIQUE (transaction_id, sequence_number)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS access_events (
                event_id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                sequence_number INTEGER NOT NULL,
                event_json TEXT NOT NULL,
                UNIQUE (transaction_id, sequence_number)
            )
            """
        )
        self._conn.commit()

    def locked(self) -> threading.RLock:
        return self._lock

    def close(self) -> None:
        with self._lock:
            if self._finalizer.alive:
                self._finalizer()

    def __enter__(self) -> "AuditStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def create_transaction(self, transaction_id: str, purpose: str, subject_ref: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO transactions(transaction_id, purpose, subject_ref, status, created_at) VALUES (?,?,?,?,?)",
                (
                    transaction_id,
                    purpose,
                    subject_ref,
                    TransactionStatus.STARTED.value,
                    datetime.now(UTC).isoformat(),
                ),
            )
            self._conn.commit()

    def set_status(
        self,
        transaction_id: str,
        status: TransactionStatus,
        ended_at: datetime | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE transactions SET status = ?, ended_at = COALESCE(?, ended_at) WHERE transaction_id = ?",
                (status.value, ended_at.isoformat() if ended_at else None, transaction_id),
            )
            self._conn.commit()

    def append_event(self, event: AuditEventRecord) -> None:
        payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
        with self._lock:
            existing = self.list_events(event.transaction_id)
            if existing and existing[-1].event_type.value == "integrity.proof_committed":
                raise ValueError("cannot append to a sealed transaction")
            self._conn.execute(
                "INSERT INTO events(event_id, transaction_id, sequence_number, event_json) VALUES (?,?,?,?)",
                (event.event_id, event.transaction_id, event.sequence_number, payload),
            )
            self._conn.commit()

    def append_access_event(self, event: AuditEventRecord) -> None:
        payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT INTO access_events(event_id, transaction_id, sequence_number, event_json) VALUES (?,?,?,?)",
                (event.event_id, event.transaction_id, event.sequence_number, payload),
            )
            self._conn.commit()

    def list_events(self, transaction_id: str) -> list[AuditEventRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT event_json FROM events WHERE transaction_id = ? ORDER BY sequence_number ASC",
                (transaction_id,),
            ).fetchall()
        return [AuditEventRecord.model_validate_json(row[0]) for row in rows]

    def list_access_events(self, transaction_id: str) -> list[AuditEventRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT event_json FROM access_events WHERE transaction_id = ? ORDER BY sequence_number ASC",
                (transaction_id,),
            ).fetchall()
        return [AuditEventRecord.model_validate_json(row[0]) for row in rows]

    def get_transaction(self, transaction_id: str) -> dict[str, str | None]:
        with self._lock:
            row = self._conn.execute(
                "SELECT transaction_id, purpose, subject_ref, status, created_at, ended_at FROM transactions WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
        if row is None:
            raise KeyError(transaction_id)
        return {
            "transaction_id": row[0],
            "purpose": row[1],
            "subject_ref": row[2],
            "status": row[3],
            "created_at": row[4],
            "ended_at": row[5],
        }

    def list_transactions(self) -> list[dict[str, str | None]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT transaction_id, purpose, subject_ref, status, created_at, ended_at FROM transactions ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "transaction_id": row[0],
                "purpose": row[1],
                "subject_ref": row[2],
                "status": row[3],
                "created_at": row[4],
                "ended_at": row[5],
            }
            for row in rows
        ]
