"""Submission Queue service - manage packages ready for translation submission."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from debconf_translation_manager.services.settings import Settings

log = logging.getLogger(__name__)


@dataclass
class QueueItem:
    """An item in the submission queue."""
    package: str
    po_path: str
    translated: int
    fuzzy: int
    untranslated: int
    total: int
    date_added: str
    language_code: str = "sv"
    
    @property
    def percentage(self) -> int:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0
        return int((self.translated / self.total) * 100)


class SubmissionQueue:
    """Manages the submission queue with persistence to JSON."""
    
    _instance: SubmissionQueue | None = None
    
    def __init__(self) -> None:
        self._queue_file = Path.home() / ".config" / "debconf-translation-manager" / "queue.json"
        self._queue_file.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[QueueItem] = []
        self._load_queue()
    
    @classmethod
    def get(cls) -> SubmissionQueue:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = SubmissionQueue()
        return cls._instance
    
    def _load_queue(self) -> None:
        """Load queue from JSON file."""
        if not self._queue_file.exists():
            return
        
        try:
            with open(self._queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._items = [QueueItem(**item) for item in data.get('items', [])]
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            log.error("Failed to load queue: %s", exc)
            self._items = []
    
    def _save_queue(self) -> None:
        """Save queue to JSON file."""
        try:
            with open(self._queue_file, 'w', encoding='utf-8') as f:
                data = {'items': [asdict(item) for item in self._items]}
                json.dump(data, f, indent=2, ensure_ascii=False)
        except (OSError, TypeError) as exc:
            log.error("Failed to save queue: %s", exc)
    
    def add_package(self, package: str, po_path: str, translated: int, fuzzy: int, untranslated: int) -> bool:
        """Add a package to the submission queue. Returns True if added, False if already exists."""
        # Check if package already in queue
        if any(item.package == package for item in self._items):
            return False
        
        total = translated + fuzzy + untranslated
        item = QueueItem(
            package=package,
            po_path=po_path,
            translated=translated,
            fuzzy=fuzzy,
            untranslated=untranslated,
            total=total,
            date_added=datetime.now().isoformat(),
            language_code=Settings.get().language_code
        )
        
        self._items.append(item)
        self._save_queue()
        return True
    
    def remove_package(self, package: str) -> bool:
        """Remove a package from the queue. Returns True if removed, False if not found."""
        original_len = len(self._items)
        self._items = [item for item in self._items if item.package != package]
        
        if len(self._items) < original_len:
            self._save_queue()
            return True
        return False
    
    def get_items(self) -> list[QueueItem]:
        """Get all queue items."""
        return self._items.copy()
    
    def is_in_queue(self, package: str) -> bool:
        """Check if a package is already in the queue."""
        return any(item.package == package for item in self._items)
    
    def clear_queue(self) -> None:
        """Clear all items from the queue."""
        self._items.clear()
        self._save_queue()
    
    def get_item_by_package(self, package: str) -> QueueItem | None:
        """Get a specific queue item by package name."""
        for item in self._items:
            if item.package == package:
                return item
        return None