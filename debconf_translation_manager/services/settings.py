"""Settings service — persist user preferences to disk."""

from __future__ import annotations

import gettext
import json
import logging
from pathlib import Path
from typing import Any

_ = gettext.gettext
log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "debconf-translation-manager"
_SETTINGS_FILE = _CONFIG_DIR / "settings.json"

_DEFAULTS: dict[str, Any] = {
    "translator_name": "",
    "translator_email": "",
    "language_code": "sv",
    "language_name": "Swedish",
    "bts_severity": "wishlist",
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_use_tls": True,
}


class Settings:
    """Singleton-style settings manager.

    Reads from ``~/.config/debconf-translation-manager/settings.json``
    on first access and writes back on :meth:`save`.
    """

    _instance: Settings | None = None

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self._loaded = False

    @classmethod
    def get(cls) -> Settings:
        """Return the shared settings instance (auto-loads from disk)."""
        if cls._instance is None:
            cls._instance = Settings()
            cls._instance.load()
        return cls._instance

    # -- persistence -------------------------------------------------------

    def load(self) -> None:
        """Load settings from disk, merging with defaults."""
        if _SETTINGS_FILE.exists():
            try:
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as fh:
                    on_disk = json.load(fh)
                self._data.update(on_disk)
                log.info("Settings loaded from %s", _SETTINGS_FILE)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Could not read settings: %s", exc)
        self._loaded = True

    def save(self) -> None:
        """Persist current settings to disk."""
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
            log.info("Settings saved to %s", _SETTINGS_FILE)
        except OSError as exc:
            log.error("Could not save settings: %s", exc)

    # -- accessors ---------------------------------------------------------

    def __getitem__(self, key: str) -> Any:
        return self._data.get(key, _DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    @property
    def translator_name(self) -> str:
        return self._data.get("translator_name", "")

    @property
    def translator_email(self) -> str:
        return self._data.get("translator_email", "")

    @property
    def language_code(self) -> str:
        return self._data.get("language_code", "sv")

    @property
    def language_name(self) -> str:
        return self._data.get("language_name", "Swedish")

    @property
    def bts_severity(self) -> str:
        return self._data.get("bts_severity", "wishlist")
