"""Preview dialog — show full email before sending to BTS."""

from __future__ import annotations

import gettext
from typing import Any, Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

_ = gettext.gettext


class PreviewDialog:
    """Adw.Dialog showing the full email that will be sent to the BTS.

    Parameters
    ----------
    parent : Adw.ApplicationWindow
        Parent window for presenting the dialog.
    item : dict
        Queue item with keys: package, subject, body, po_file_path,
        severity, tags, language, language_name.
    on_send : callable(item) | None
        Called when user clicks "Confirm & Send".
    on_edit : callable(item) | None
        Called when user clicks "Edit & Close".
    """

    def __init__(
        self,
        parent: Adw.ApplicationWindow,
        item: dict[str, Any],
        on_send: Callable[[dict[str, Any]], None] | None = None,
        on_edit: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._item = item
        self._on_send = on_send
        self._on_edit = on_edit

        dialog = Adw.Dialog()
        dialog.set_title(_("Email Preview"))
        dialog.set_content_width(650)
        dialog.set_content_height(550)
        self._dialog = dialog

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()

        edit_btn = Gtk.Button(label=_("Edit & Close"))
        edit_btn.connect("clicked", self._on_edit_clicked)
        header.pack_start(edit_btn)

        send_btn = Gtk.Button(label=_("Confirm & Send"))
        send_btn.add_css_class("suggested-action")
        send_btn.connect("clicked", self._on_send_clicked)
        header.pack_end(send_btn)

        toolbar.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        # To
        to_label = Gtk.Label(
            label=_("To: submit@bugs.debian.org"),
            xalign=0,
        )
        to_label.add_css_class("heading")
        content.append(to_label)

        # Subject
        subj_label = Gtk.Label(
            label=_("Subject: %s") % item.get("subject", ""),
            xalign=0,
            wrap=True,
        )
        subj_label.add_css_class("dim-label")
        content.append(subj_label)

        content.append(Gtk.Separator())

        # Headers summary
        headers_text = (
            f"Package: {item.get('package', '')}\n"
            f"Severity: {item.get('severity', 'wishlist')}\n"
            f"Tags: {item.get('tags', 'l10n patch')}"
        )
        headers_label = Gtk.Label(label=headers_text, xalign=0)
        headers_label.add_css_class("monospace")
        headers_label.add_css_class("caption")
        content.append(headers_label)

        content.append(Gtk.Separator())

        # Body
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD)
        tv.set_left_margin(8)
        tv.set_right_margin(8)
        tv.set_top_margin(8)
        tv.set_bottom_margin(8)
        tv.add_css_class("monospace")
        tv.get_buffer().set_text(item.get("body", ""))
        scroll.set_child(tv)

        body_frame = Gtk.Frame()
        body_frame.set_child(scroll)
        content.append(body_frame)

        # Attachment
        po_path = item.get("po_file_path", "")
        if po_path:
            att_label = Gtk.Label(
                label=_("Attachment: %s") % po_path,
                xalign=0,
            )
            att_label.add_css_class("caption")
            att_label.set_margin_top(4)
            content.append(att_label)

        toolbar.set_content(content)
        dialog.set_child(toolbar)
        dialog.present(parent)

    def _on_edit_clicked(self, btn: Gtk.Button) -> None:
        self._dialog.close()
        if self._on_edit:
            self._on_edit(self._item)

    def _on_send_clicked(self, btn: Gtk.Button) -> None:
        self._dialog.close()
        if self._on_send:
            self._on_send(self._item)
