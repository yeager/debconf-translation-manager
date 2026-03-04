"""Change notification service.

Detects when debconf templates change (new/modified strings) and
emits desktop notifications.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GLib

log = logging.getLogger(__name__)


@dataclass
class TemplateChange:
    """A detected template change."""

    package: str
    template_name: str
    change_type: str  # added, modified, removed
    field: str  # Description, Extended description, Choices, etc.
    old_value: str = ""
    new_value: str = ""
    detected_at: str = ""

    def __post_init__(self) -> None:
        if not self.detected_at:
            self.detected_at = datetime.now().isoformat()


class ChangeNotifier:
    """Monitors for template changes and notifies the UI."""

    def __init__(self) -> None:
        self._listeners: list[Callable[[list[TemplateChange]], None]] = []
        self._changes: list[TemplateChange] = []
        self._poll_source_id: int | None = None

    def add_listener(self, callback: Callable[[list[TemplateChange]], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[list[TemplateChange]], None]) -> None:
        self._listeners.remove(callback)

    def start_polling(self, interval_seconds: int = 300) -> None:
        """Start periodic polling for changes."""
        if self._poll_source_id is not None:
            return
        self._poll_source_id = GLib.timeout_add_seconds(
            interval_seconds, self._poll_tick
        )
        log.info("Started change polling every %ds", interval_seconds)

    def stop_polling(self) -> None:
        if self._poll_source_id is not None:
            GLib.source_remove(self._poll_source_id)
            self._poll_source_id = None

    def check_now(self) -> list[TemplateChange]:
        """Manually trigger a check. Returns detected changes."""
        changes = self._detect_changes()
        if changes:
            self._changes.extend(changes)
            self._notify_listeners(changes)
            self._send_desktop_notification(changes)
        return changes

    def get_all_changes(self) -> list[TemplateChange]:
        return list(self._changes)

    def clear_changes(self) -> None:
        self._changes.clear()

    def load_mock_changes(self) -> list[TemplateChange]:
        """Load mock changes for testing."""
        changes = get_mock_changes()
        self._changes.extend(changes)
        self._notify_listeners(changes)
        return changes

    # -- internal -------------------------------------------------------

    def _poll_tick(self) -> bool:
        """GLib timeout callback."""
        self.check_now()
        return True  # keep ticking

    def _detect_changes(self) -> list[TemplateChange]:
        """Detect template changes.

        In production this would compare cached templates against
        freshly downloaded ones. For now return empty.
        """
        return []

    def _notify_listeners(self, changes: list[TemplateChange]) -> None:
        for listener in self._listeners:
            try:
                listener(changes)
            except Exception as exc:
                log.error("Listener error: %s", exc)

    def _send_desktop_notification(self, changes: list[TemplateChange]) -> None:
        """Send a desktop notification about template changes."""
        try:
            app = Gio.Application.get_default()
            if app is None:
                return

            notif = Gio.Notification.new("Debconf Template Changes")
            packages = {c.package for c in changes}
            body = f"{len(changes)} change(s) in: {', '.join(sorted(packages))}"
            notif.set_body(body)
            app.send_notification("template-changes", notif)
        except Exception as exc:
            log.debug("Desktop notification failed: %s", exc)


# ── Mock data ─────────────────────────────────────────────────────────

def get_mock_changes() -> list[TemplateChange]:
    return [
        TemplateChange(
            package="grub-pc",
            template_name="grub-pc/install_devices",
            change_type="modified",
            field="Description",
            old_value="GRUB install devices:",
            new_value="GRUB install devices",
            detected_at="2026-03-01T10:30:00",
        ),
        TemplateChange(
            package="locales",
            template_name="locales/locales_to_be_generated",
            change_type="modified",
            field="Extended description",
            old_value=(
                "Select the locales you want to generate. The selection "
                "will be saved to '/etc/locale.gen'."
            ),
            new_value=(
                "Select the locales you want to be generated. The selection "
                "will be saved to '/etc/locale.gen'. The selected locales will "
                "be generated when you finish configuring locales."
            ),
            detected_at="2026-03-02T14:15:00",
        ),
        TemplateChange(
            package="cloud-init",
            template_name="cloud-init/datasources",
            change_type="added",
            field="Description",
            old_value="",
            new_value="Which cloud datasources should be read?",
            detected_at="2026-03-03T09:00:00",
        ),
        TemplateChange(
            package="openssh-server",
            template_name="openssh-server/permit-root-login",
            change_type="removed",
            field="Description",
            old_value="Permit root login via SSH?",
            new_value="",
            detected_at="2026-03-03T09:00:00",
        ),
        TemplateChange(
            package="keyboard-configuration",
            template_name="keyboard-configuration/model",
            change_type="modified",
            field="Extended description",
            old_value="Please select the model of keyboard of this machine.",
            new_value="Please select the model of the keyboard of this machine.",
            detected_at="2026-03-04T08:00:00",
        ),
    ]
