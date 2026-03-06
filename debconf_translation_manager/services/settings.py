"""Settings service — persist user preferences to disk."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "debconf-translation-manager"
_SETTINGS_FILE = _CONFIG_DIR / "settings.json"

_DEFAULTS: dict[str, Any] = {
    "translator_name": "",
    "translator_email": "",
    "language_code": "sv",
    "language_name": "Swedish",
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "smtp_use_tls": True,
    "email_from": "",
    "default_cc": "debian-l10n-swedish@lists.debian.org",
    "cache_dir": str(Path.home() / ".cache" / "debconf-translation-manager"),
}


class Settings:
    """Singleton settings manager backed by JSON on disk."""

    _instance: Settings | None = None

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self._loaded = False

    @classmethod
    def get(cls) -> Settings:
        if cls._instance is None:
            cls._instance = Settings()
            cls._instance.load()
        return cls._instance

    def load(self) -> None:
        if _SETTINGS_FILE.exists():
            try:
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as fh:
                    on_disk = json.load(fh)
                self._data.update(on_disk)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Could not read settings: %s", exc)
        self._loaded = True

    def save(self) -> None:
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            log.error("Could not save settings: %s", exc)

    def __getitem__(self, key: str) -> Any:
        return self._data.get(key, _DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    @property
    def language_code(self) -> str:
        return self._data.get("language_code", "sv")

    @property
    def cache_dir(self) -> Path:
        d = Path(self._data.get("cache_dir", _DEFAULTS["cache_dir"]))
        d.mkdir(parents=True, exist_ok=True)
        return d
