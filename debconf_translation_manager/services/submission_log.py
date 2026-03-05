"""Submission history log — track filed BTS bug reports."""

from __future__ import annotations

import gettext
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

_ = gettext.gettext
log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "debconf-translation-manager"
_LOG_FILE = _CONFIG_DIR / "submission_log.json"


class SubmissionLog:
    """Persists a list of submitted bug reports to disk."""

    _instance: SubmissionLog | None = None

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    @classmethod
    def get(cls) -> SubmissionLog:
        if cls._instance is None:
            cls._instance = SubmissionLog()
            cls._instance.load()
        return cls._instance

    # -- persistence -------------------------------------------------------

    def load(self) -> None:
        if _LOG_FILE.exists():
            try:
                with open(_LOG_FILE, "r", encoding="utf-8") as fh:
                    self._entries = json.load(fh)
                log.info("Submission log loaded: %d entries", len(self._entries))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Could not read submission log: %s", exc)

    def save(self) -> None:
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(_LOG_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._entries, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            log.error("Could not save submission log: %s", exc)

    # -- accessors ---------------------------------------------------------

    @property
    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def add(
        self,
        package: str,
        subject: str,
        language: str,
        status: str = "filed",
        bug_number: str = "",
        tags: list[str] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        """Record a new submission and persist."""
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "package": package,
            "subject": subject,
            "language": language,
            "status": status,
            "bug_number": bug_number,
            "tags": tags or [],
            "notes": notes,
        }
        self._entries.insert(0, entry)
        self.save()
        return entry

    def update_entry(self, index: int, **kwargs: Any) -> None:
        """Update fields on an entry by index."""
        if 0 <= index < len(self._entries):
            self._entries[index].update(kwargs)
            self.save()

    def previously_submitted_packages(self) -> list[str]:
        """Return unique package names that have been submitted."""
        seen: set[str] = set()
        result: list[str] = []
        for e in self._entries:
            pkg = e.get("package", "")
            if pkg and pkg not in seen:
                seen.add(pkg)
                result.append(pkg)
        return result

    def get_mock_entries(self) -> list[dict[str, Any]]:
        """Return sample entries for offline testing."""
        return [
            {
                "timestamp": "2026-01-22T14:30:00",
                "package": "popularity-contest",
                "subject": "[INTL:sv] Swedish debconf translation for popularity-contest",
                "language": "sv",
                "status": "filed",
            },
            {
                "timestamp": "2026-01-10T10:15:00",
                "package": "grub-pc",
                "subject": "[INTL:sv] Swedish debconf translation for grub-pc",
                "language": "sv",
                "status": "filed",
            },
            {
                "timestamp": "2025-12-01T09:00:00",
                "package": "locales",
                "subject": "[INTL:sv] Swedish debconf translation for locales",
                "language": "sv",
                "status": "accepted",
            },
            {
                "timestamp": "2025-11-15T16:45:00",
                "package": "tzdata",
                "subject": "[INTL:sv] Swedish debconf translation for tzdata",
                "language": "sv",
                "status": "accepted",
            },
            {
                "timestamp": "2025-09-05T11:20:00",
                "package": "dash",
                "subject": "[INTL:sv] Swedish debconf translation for dash",
                "language": "sv",
                "status": "accepted",
            },
        ]
