"""Submission log — SQLite-backed history of translation submissions."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from debconf_translation_manager.services.settings import Settings

log = logging.getLogger(__name__)


@dataclass
class SubmissionRecord:
    id: int
    package: str
    language: str
    timestamp: str
    recipient: str
    subject: str
    po_path: str
    translated: int
    fuzzy: int
    untranslated: int


class SubmissionLog:
    """SQLite-backed submission history."""

    _instance: SubmissionLog | None = None

    def __init__(self) -> None:
        db_path = Settings.get().cache_dir / "submissions.db"
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    @classmethod
    def get(cls) -> SubmissionLog:
        if cls._instance is None:
            cls._instance = SubmissionLog()
        return cls._instance

    def _create_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package TEXT NOT NULL,
                language TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                recipient TEXT,
                subject TEXT,
                po_path TEXT,
                translated INTEGER DEFAULT 0,
                fuzzy INTEGER DEFAULT 0,
                untranslated INTEGER DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stats_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                language TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                total_packages INTEGER,
                translated_packages INTEGER,
                percentage REAL
            )
        """)
        self._conn.commit()

    def log_submission(
        self,
        package: str,
        language: str,
        recipient: str,
        subject: str,
        po_path: str,
        translated: int = 0,
        fuzzy: int = 0,
        untranslated: int = 0,
    ) -> None:
        self._conn.execute(
            """INSERT INTO submissions
               (package, language, timestamp, recipient, subject, po_path,
                translated, fuzzy, untranslated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                package,
                language,
                datetime.now().isoformat(),
                recipient,
                subject,
                po_path,
                translated,
                fuzzy,
                untranslated,
            ),
        )
        self._conn.commit()

    def get_package_history(self, package: str) -> list[SubmissionRecord]:
        rows = self._conn.execute(
            "SELECT * FROM submissions WHERE package = ? ORDER BY timestamp DESC",
            (package,),
        ).fetchall()
        return [SubmissionRecord(**dict(r)) for r in rows]

    def get_all_submissions(self) -> list[SubmissionRecord]:
        rows = self._conn.execute(
            "SELECT * FROM submissions ORDER BY timestamp DESC"
        ).fetchall()
        return [SubmissionRecord(**dict(r)) for r in rows]

    def log_stats_snapshot(
        self,
        language: str,
        total_packages: int,
        translated_packages: int,
        percentage: float,
    ) -> None:
        self._conn.execute(
            """INSERT INTO stats_snapshots
               (language, timestamp, total_packages, translated_packages, percentage)
               VALUES (?, ?, ?, ?, ?)""",
            (
                language,
                datetime.now().isoformat(),
                total_packages,
                translated_packages,
                percentage,
            ),
        )
        self._conn.commit()

    def get_stats_history(self, language: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM stats_snapshots WHERE language = ? ORDER BY timestamp",
            (language,),
        ).fetchall()
        return [dict(r) for r in rows]

    def export_csv(self) -> str:
        """Export all submissions as CSV."""
        rows = self.get_all_submissions()
        lines = ["package,language,timestamp,recipient,translated,fuzzy,untranslated"]
        for r in rows:
            lines.append(
                f"{r.package},{r.language},{r.timestamp},{r.recipient},"
                f"{r.translated},{r.fuzzy},{r.untranslated}"
            )
        return "\n".join(lines)
