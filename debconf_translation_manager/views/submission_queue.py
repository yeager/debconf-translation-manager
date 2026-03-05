"""Submission Queue view — manage translations pending BTS submission."""

from __future__ import annotations

import gettext
import smtplib
import threading
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from debconf_translation_manager.services.settings import Settings
from debconf_translation_manager.services.submission_log import SubmissionLog
from debconf_translation_manager.services.submission_queue import SubmissionQueue
from debconf_translation_manager.widgets.preview_dialog import PreviewDialog
from debconf_translation_manager.widgets.status_badge import StatusBadge

_ = gettext.gettext


class SubmissionQueueView(Gtk.Box):
    """View showing translations queued for BTS submission."""

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._queue = SubmissionQueue.get()
        self._submission_log = SubmissionLog.get()
        self._build_ui()
        self._refresh()

    def focus_search(self) -> None:
        pass

    def get_export_data(self) -> list[dict[str, Any]]:
        return self._queue.items

    def refresh(self) -> None:
        """Public refresh for external callers."""
        self._refresh()

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        # Title
        title = Gtk.Label(label=_("Submission Queue"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_margin_start(16)
        title.set_margin_top(12)
        title.set_margin_bottom(4)
        self.append(title)

        subtitle = Gtk.Label(
            label=_("Translations queued for submission to the Debian BTS"),
            xalign=0,
        )
        subtitle.add_css_class("dim-label")
        subtitle.set_margin_start(16)
        subtitle.set_margin_bottom(8)
        self.append(subtitle)

        # Send All button row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_start(16)
        btn_row.set_margin_end(16)
        btn_row.set_margin_bottom(8)

        self._send_all_btn = Gtk.Button(label=_("Send All"))
        self._send_all_btn.add_css_class("suggested-action")
        self._send_all_btn.connect("clicked", self._on_send_all)
        btn_row.append(self._send_all_btn)

        self._count_label = Gtk.Label(label="")
        self._count_label.add_css_class("dim-label")
        self._count_label.set_hexpand(True)
        self._count_label.set_xalign(0)
        self._count_label.set_margin_start(8)
        btn_row.append(self._count_label)

        self.append(btn_row)
        self.append(Gtk.Separator())

        # Queue list
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(16)
        self._list_box.set_margin_end(16)
        self._list_box.set_margin_top(8)
        self._list_box.set_margin_bottom(8)
        scroll.set_child(self._list_box)

        # Empty state
        self._empty_status = Adw.StatusPage()
        self._empty_status.set_icon_name("mail-send-symbolic")
        self._empty_status.set_title(_("Queue is empty"))
        self._empty_status.set_description(
            _("Use the Coordination view to queue packages for submission.")
        )

        self._content_stack = Gtk.Stack()
        self._content_stack.add_named(scroll, "list")
        self._content_stack.add_named(self._empty_status, "empty")
        self._content_stack.set_vexpand(True)
        self.append(self._content_stack)

    def _refresh(self) -> None:
        """Rebuild the queue list from persisted data."""
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        items = self._queue.items
        queued = [i for i in items if i.get("status") == "queued"]

        if not queued:
            self._content_stack.set_visible_child_name("empty")
            self._send_all_btn.set_sensitive(False)
            self._count_label.set_label("")
            return

        self._content_stack.set_visible_child_name("list")
        self._send_all_btn.set_sensitive(True)
        self._count_label.set_label(
            _("%d item(s) in queue") % len(queued)
        )

        for item in queued:
            row = self._make_queue_row(item)
            self._list_box.append(row)

    def _make_queue_row(self, item: dict[str, Any]) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_activatable(False)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_margin_start(8)
        outer.set_margin_end(8)
        outer.set_margin_top(8)
        outer.set_margin_bottom(8)

        # Top: package name + status badge + date
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        pkg_label = Gtk.Label(label=item.get("package", ""), xalign=0)
        pkg_label.add_css_class("heading")
        pkg_label.set_hexpand(True)
        top.append(pkg_label)

        lang_label = Gtk.Label(label=item.get("language", ""))
        lang_label.add_css_class("caption")
        top.append(lang_label)

        badge = StatusBadge(status=item.get("status", "queued"))
        top.append(badge)

        ts = item.get("timestamp", "")[:10]
        date_label = Gtk.Label(label=ts)
        date_label.add_css_class("caption")
        date_label.add_css_class("dim-label")
        top.append(date_label)

        outer.append(top)

        # Subject line
        subj_label = Gtk.Label(label=item.get("subject", ""), xalign=0)
        subj_label.add_css_class("caption")
        subj_label.add_css_class("dim-label")
        subj_label.set_ellipsize(3)
        outer.append(subj_label)

        # Action buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_box.set_margin_top(4)

        preview_btn = Gtk.Button(label=_("Preview"))
        preview_btn.add_css_class("flat")
        item_id = item.get("id", "")
        preview_btn.connect("clicked", lambda b, iid=item_id: self._on_preview(iid))
        btn_box.append(preview_btn)

        edit_btn = Gtk.Button(label=_("Edit"))
        edit_btn.add_css_class("flat")
        edit_btn.connect("clicked", lambda b, iid=item_id: self._on_edit(iid))
        btn_box.append(edit_btn)

        send_btn = Gtk.Button(label=_("Send"))
        send_btn.add_css_class("suggested-action")
        send_btn.add_css_class("flat")
        send_btn.connect("clicked", lambda b, iid=item_id: self._on_send(iid))
        btn_box.append(send_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_box.append(spacer)

        remove_btn = Gtk.Button(icon_name="user-trash-symbolic")
        remove_btn.add_css_class("flat")
        remove_btn.add_css_class("destructive-action")
        remove_btn.set_tooltip_text(_("Remove from queue"))
        remove_btn.connect("clicked", lambda b, iid=item_id: self._on_remove(iid))
        btn_box.append(remove_btn)

        outer.append(btn_box)
        row.set_child(outer)
        return row

    # -- callbacks ------------------------------------------------------

    def _on_preview(self, item_id: str) -> None:
        item = self._queue.get_item(item_id)
        if not item or not self._window:
            return
        # Ensure body is populated
        if not item.get("body"):
            item["body"] = self._generate_body(item)
        PreviewDialog(
            parent=self._window,
            item=item,
            on_send=lambda i: self._send_item(i.get("id", "")),
            on_edit=lambda i: self._on_edit(i.get("id", "")),
        )

    def _on_edit(self, item_id: str) -> None:
        """Open the .po file in the PO editor."""
        item = self._queue.get_item(item_id)
        if not item or not self._window:
            return
        po_path = item.get("po_file_path", "")
        pkg = item.get("package", "")
        self._window.navigate_to_editor(package=pkg, po_file_path=po_path or None)

    def _on_send(self, item_id: str) -> None:
        self._send_item(item_id)

    def _on_remove(self, item_id: str) -> None:
        self._queue.remove(item_id)
        self._refresh()
        if self._window:
            self._window.show_toast(_("Removed from queue"))

    def _on_send_all(self, btn: Gtk.Button) -> None:
        items = [i for i in self._queue.items if i.get("status") == "queued"]
        if not items:
            return
        for item in items:
            self._send_item(item.get("id", ""))

    # -- SMTP sending ---------------------------------------------------

    def _send_item(self, item_id: str) -> None:
        """Send a queued item via SMTP in a background thread."""
        item = self._queue.get_item(item_id)
        if not item:
            return

        settings = Settings.get()
        host = settings["smtp_host"]
        if not host:
            if self._window:
                self._window.show_toast(
                    _("SMTP not configured -- go to Settings first")
                )
            return

        from_addr = settings.translator_email
        if not from_addr:
            if self._window:
                self._window.show_toast(_("Set your email in Settings first"))
            return

        # Generate body if empty
        if not item.get("body"):
            item["body"] = self._generate_body(item)

        def do_send() -> None:
            try:
                subject = item.get("subject", "")
                body = item.get("body", "")
                po_path = item.get("po_file_path", "")

                # Build email
                if po_path and Path(po_path).exists():
                    msg = MIMEMultipart()
                    msg.attach(MIMEText(body, "plain", "utf-8"))
                    with open(po_path, "rb") as f:
                        att = MIMEApplication(f.read(), Name=Path(po_path).name)
                    att["Content-Disposition"] = (
                        f'attachment; filename="{Path(po_path).name}"'
                    )
                    msg.attach(att)
                else:
                    msg = MIMEText(body, "plain", "utf-8")

                msg["Subject"] = subject
                msg["From"] = from_addr
                msg["To"] = "submit@bugs.debian.org"

                port = int(settings["smtp_port"])
                use_tls = settings["smtp_use_tls"]

                server = smtplib.SMTP(host, port, timeout=30)
                if use_tls:
                    server.starttls()
                server.sendmail(from_addr, ["submit@bugs.debian.org"], msg.as_string())
                server.quit()

                # Log to submission history
                self._submission_log.add(
                    package=item.get("package", ""),
                    subject=subject,
                    language=item.get("language", ""),
                    status="sent",
                )

                # Remove from queue
                self._queue.remove(item_id)

                GLib.idle_add(self._on_send_success, item.get("package", ""))

            except Exception as exc:
                GLib.idle_add(self._on_send_error, str(exc))

        thread = threading.Thread(target=do_send, daemon=True)
        thread.start()

    def _on_send_success(self, package: str) -> bool:
        self._refresh()
        if self._window:
            self._window.show_toast(_("Sent: %s") % package)
        return False

    def _on_send_error(self, error: str) -> bool:
        if self._window:
            self._window.show_toast(_("Send failed: %s") % error)
        return False

    def _generate_body(self, item: dict[str, Any]) -> str:
        """Generate the email body for a queue item."""
        settings = Settings.get()
        name = settings.translator_name or _("Translator Name")
        email = settings.translator_email or "translator@example.com"
        pkg = item.get("package", "PACKAGE")
        lang_name = item.get("language_name", settings.language_name)
        severity = item.get("severity", "wishlist")
        tags = item.get("tags", "l10n patch")

        return (
            f"Package: {pkg}\n"
            f"Severity: {severity}\n"
            f"Tags: {tags}\n"
            f"\n"
            f"Please find attached the {lang_name} debconf translation for {pkg}.\n"
            f"\n"
            f"This translation has been reviewed by the {lang_name} l10n team.\n"
            f"\n"
            f"Translators:\n"
            f"  - {name} <{email}>\n"
        )
