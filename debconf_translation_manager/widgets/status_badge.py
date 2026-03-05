"""Status badge widget — colored pill showing translation status."""

from __future__ import annotations

import gettext

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

_ = gettext.gettext

# Status → (CSS class, display label)
_STATUS_MAP: dict[str, tuple[str, str]] = {
    "translated": ("success", _("Translated")),
    "untranslated": ("error", _("Untranslated")),
    "fuzzy": ("warning", _("Fuzzy")),
    "pending-review": ("accent", _("Pending Review")),
    "reviewed": ("success", _("Reviewed")),
    "accepted": ("success", _("Accepted")),
    "open": ("warning", _("Open")),
    "added": ("success", _("Added")),
    "modified": ("warning", _("Modified")),
    "removed": ("error", _("Removed")),
    "queued": ("accent", _("Queued")),
    "sent": ("success", _("Sent")),
    "filed": ("success", _("Filed")),
}


class StatusBadge(Gtk.Label):
    """A small pill-shaped label showing a translation status."""

    def __init__(self, status: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.add_css_class("caption")
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.CENTER)
        if status:
            self.set_status(status)

    def set_status(self, status: str) -> None:
        css_class, label = _STATUS_MAP.get(
            status, ("dim-label", status.replace("-", " ").title())
        )

        # Remove old status classes
        for cls in ("success", "error", "warning", "accent", "dim-label"):
            self.remove_css_class(cls)

        self.set_label(label)
        self.add_css_class(css_class)
        self.add_css_class("pill-badge")
