"""Submission queue — track translations pending BTS submission."""

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
_QUEUE_FILE = _CONFIG_DIR / "submission_queue.json"


class SubmissionQueue:
    """Persists a list of queued translation submissions to disk."""

    _instance: SubmissionQueue | None = None

    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    @classmethod
    def get(cls) -> SubmissionQueue:
        if cls._instance is None:
            cls._instance = SubmissionQueue()
            cls._instance.load()
        return cls._instance

    # -- persistence -----------------------------------------------------------

    def load(self) -> None:
        if _QUEUE_FILE.exists():
            try:
                with open(_QUEUE_FILE, "r", encoding="utf-8") as fh:
                    self._items = json.load(fh)
                log.info("Submission queue loaded: %d items", len(self._items))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Could not read submission queue: %s", exc)

    def save(self) -> None:
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(_QUEUE_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._items, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            log.error("Could not save submission queue: %s", exc)

    # -- accessors -------------------------------------------------------------

    @property
    def items(self) -> list[dict[str, Any]]:
        return list(self._items)

    def add(
        self,
        package: str,
        language: str,
        language_name: str,
        po_file_path: str,
        subject: str = "",
        body: str = "",
        severity: str = "wishlist",
        tags: str = "l10n patch",
    ) -> dict[str, Any]:
        """Add a translation to the submission queue."""
        if not subject:
            subject = f"[INTL:{language}] {language_name} debconf translation for {package}"
        item = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S") + f"-{package}",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "package": package,
            "language": language,
            "language_name": language_name,
            "subject": subject,
            "body": body,
            "po_file_path": po_file_path,
            "severity": severity,
            "tags": tags,
            "status": "queued",
        }
        self._items.insert(0, item)
        self.save()
        return item

    def remove(self, item_id: str) -> None:
        """Remove an item from the queue by its id."""
        self._items = [i for i in self._items if i.get("id") != item_id]
        self.save()

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        """Get a queue item by id."""
        for item in self._items:
            if item.get("id") == item_id:
                return item
        return None

    def update_item(self, item_id: str, **kwargs: Any) -> None:
        """Update fields on a queue item."""
        for item in self._items:
            if item.get("id") == item_id:
                item.update(kwargs)
                self.save()
                return
