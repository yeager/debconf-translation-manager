"""BTS Workflow view — compose l10n bug reports, attach .po files,
track filed bugs against the Debian Bug Tracking System."""

from __future__ import annotations

import gettext
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from debconf_translation_manager.services.l10n_debian import (
    fetch_and_parse,
)
from debconf_translation_manager.services.settings import Settings
from debconf_translation_manager.services.submission_log import SubmissionLog
from debconf_translation_manager.widgets.filter_bar import FilterBar
from debconf_translation_manager.widgets.status_badge import StatusBadge

_ = gettext.gettext


class BTSWorkflowView(Gtk.Box):
    """Compose and track l10n bug reports for the Debian BTS.

    Subject format: [INTL:sv] Swedish debconf translation for PACKAGE
    """

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        settings = Settings.get()
        self._language = settings.language_code
        self._language_name = settings.language_name
        self._filed_bugs: list[dict[str, str]] = _get_mock_filed_bugs()
        self._submission_log = SubmissionLog.get()
        self._build_ui()

    def focus_search(self) -> None:
        self._filter_bar.focus_search()

    def get_export_data(self) -> list[dict[str, Any]]:
        return self._filed_bugs

    def prefill(
        self,
        package: str | None = None,
        po_file_path: str | None = None,
    ) -> None:
        """Pre-fill the compose form with package and .po file info."""
        settings = Settings.get()
        self._language = settings.language_code
        self._language_name = settings.language_name

        if package:
            self._pkg_entry.set_text(package)
        if po_file_path:
            self._attach_label.set_label(po_file_path)

        # Update body template with translator info
        self._update_body_template()

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        # Title
        title = Gtk.Label(label=_("BTS Bug Filing"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_margin_start(16)
        title.set_margin_top(12)
        title.set_margin_bottom(4)
        self.append(title)

        subtitle = Gtk.Label(
            label=_("File l10n bug reports against Debian packages with debconf translations"),
            xalign=0,
        )
        subtitle.add_css_class("dim-label")
        subtitle.set_margin_start(16)
        subtitle.set_margin_bottom(8)
        self.append(subtitle)

        self.append(Gtk.Separator())

        # Paned: compose form left, filed bugs + history right
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(550)

        # ---- Left: compose form ----
        compose_scroll = Gtk.ScrolledWindow()
        compose_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        compose_box.set_margin_start(16)
        compose_box.set_margin_end(8)
        compose_box.set_margin_top(12)
        compose_box.set_margin_bottom(12)

        compose_title = Gtk.Label(label=_("Compose Bug Report"), xalign=0)
        compose_title.add_css_class("title-4")
        compose_box.append(compose_title)

        # Package
        pkg_label = Gtk.Label(label=_("Package:"), xalign=0)
        pkg_label.add_css_class("heading")
        compose_box.append(pkg_label)

        pkg_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._pkg_entry = Gtk.Entry()
        self._pkg_entry.set_placeholder_text(_("e.g. grub-pc"))
        self._pkg_entry.set_hexpand(True)
        self._pkg_entry.connect("changed", self._on_pkg_changed)
        pkg_row.append(self._pkg_entry)

        # Quick pick from real or mock data
        pick_btn = Gtk.MenuButton(label=_("Pick…"))
        self._pick_menu = Gio.Menu()
        self._populate_pick_menu()
        pick_btn.set_menu_model(self._pick_menu)
        pkg_row.append(pick_btn)
        compose_box.append(pkg_row)

        # Language row
        lang_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lang_code_label = Gtk.Label(label=_("Language code:"), xalign=0)
        lang_code_label.add_css_class("heading")
        lang_row.append(lang_code_label)
        self._lang_entry = Gtk.Entry()
        self._lang_entry.set_text(self._language)
        self._lang_entry.set_max_width_chars(6)
        self._lang_entry.connect("changed", self._on_pkg_changed)
        lang_row.append(self._lang_entry)

        lang_name_label = Gtk.Label(label=_("Language name:"), xalign=0)
        lang_name_label.add_css_class("heading")
        lang_row.append(lang_name_label)
        self._lang_name_entry = Gtk.Entry()
        self._lang_name_entry.set_text(self._language_name)
        self._lang_name_entry.set_hexpand(True)
        self._lang_name_entry.connect("changed", self._on_pkg_changed)
        lang_row.append(self._lang_name_entry)
        compose_box.append(lang_row)

        # Auto-generated subject
        subj_label = Gtk.Label(label=_("Subject:"), xalign=0)
        subj_label.add_css_class("heading")
        compose_box.append(subj_label)

        self._subject_entry = Gtk.Entry()
        self._subject_entry.set_editable(True)
        self._subject_entry.set_text(
            f"[INTL:{self._language}] {self._language_name} debconf translation for PACKAGE"
        )
        compose_box.append(self._subject_entry)

        # Body
        body_label = Gtk.Label(label=_("Body:"), xalign=0)
        body_label.add_css_class("heading")
        compose_box.append(body_label)

        body_scroll = Gtk.ScrolledWindow()
        body_scroll.set_min_content_height(160)
        body_scroll.set_vexpand(True)

        self._body_view = Gtk.TextView()
        self._body_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._body_view.set_left_margin(8)
        self._body_view.set_right_margin(8)
        self._body_view.set_top_margin(8)
        self._body_view.set_bottom_margin(8)
        self._body_view.add_css_class("monospace")
        self._set_default_body()
        body_scroll.set_child(self._body_view)

        body_frame = Gtk.Frame()
        body_frame.set_child(body_scroll)
        compose_box.append(body_frame)

        # Attachment
        attach_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        attach_label = Gtk.Label(label=_("Attach .po file:"), xalign=0)
        attach_label.add_css_class("heading")
        attach_row.append(attach_label)

        self._attach_label = Gtk.Label(label=_("(none)"))
        self._attach_label.add_css_class("dim-label")
        self._attach_label.set_hexpand(True)
        self._attach_label.set_xalign(0)
        attach_row.append(self._attach_label)

        browse_btn = Gtk.Button(label=_("Browse…"))
        browse_btn.connect("clicked", self._on_browse_po)
        attach_row.append(browse_btn)
        compose_box.append(attach_row)

        # Severity
        sev_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sev_label = Gtk.Label(label=_("Severity:"), xalign=0)
        sev_label.add_css_class("heading")
        sev_row.append(sev_label)

        severities = ["wishlist", "minor", "normal", "important"]
        sev_model = Gtk.StringList.new(severities)
        self._sev_dd = Gtk.DropDown(model=sev_model)
        self._sev_dd.set_selected(0)
        sev_row.append(self._sev_dd)
        compose_box.append(sev_row)

        # Tags
        tag_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tag_label = Gtk.Label(label=_("Tags:"), xalign=0)
        tag_label.add_css_class("heading")
        tag_row.append(tag_label)
        self._tag_entry = Gtk.Entry()
        self._tag_entry.set_text("l10n patch")
        self._tag_entry.set_hexpand(True)
        tag_row.append(self._tag_entry)
        compose_box.append(tag_row)

        # Action buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(8)

        preview_btn = Gtk.Button(label=_("Preview Email"))
        preview_btn.connect("clicked", self._on_preview)
        btn_row.append(preview_btn)

        copy_btn = Gtk.Button(label=_("Copy to Clipboard"))
        copy_btn.connect("clicked", self._on_copy_report)
        btn_row.append(copy_btn)

        send_btn = Gtk.Button(label=_("Open in Mail Client"))
        send_btn.add_css_class("suggested-action")
        send_btn.connect("clicked", self._on_open_mail)
        btn_row.append(send_btn)

        smtp_btn = Gtk.Button(label=_("Send via SMTP"))
        smtp_btn.connect("clicked", self._on_send_smtp)
        btn_row.append(smtp_btn)

        compose_box.append(btn_row)
        compose_scroll.set_child(compose_box)
        paned.set_start_child(compose_scroll)

        # ---- Right: filed bugs + submission history ----
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_box.set_margin_start(8)
        right_box.set_margin_end(16)
        right_box.set_margin_top(12)

        right_title = Gtk.Label(label=_("Filed Bugs"), xalign=0)
        right_title.add_css_class("title-4")
        right_box.append(right_title)

        self._filter_bar = FilterBar(
            search_placeholder=_("Filter bugs…"),
            on_changed=self._apply_bug_filter,
        )
        right_box.append(self._filter_bar)

        bugs_scroll = Gtk.ScrolledWindow()
        bugs_scroll.set_vexpand(True)

        self._bugs_list = Gtk.ListBox()
        self._bugs_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._bugs_list.add_css_class("boxed-list")
        bugs_scroll.set_child(self._bugs_list)
        right_box.append(bugs_scroll)

        # -- Submission History section ------------------------------------
        right_box.append(Gtk.Separator())

        history_title = Gtk.Label(label=_("Submission History"), xalign=0)
        history_title.add_css_class("title-4")
        history_title.set_margin_top(8)
        right_box.append(history_title)

        history_scroll = Gtk.ScrolledWindow()
        history_scroll.set_vexpand(True)
        history_scroll.set_min_content_height(120)

        self._history_list = Gtk.ListBox()
        self._history_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._history_list.add_css_class("boxed-list")
        history_scroll.set_child(self._history_list)
        right_box.append(history_scroll)

        self._prev_packages_label = Gtk.Label(xalign=0, wrap=True)
        self._prev_packages_label.add_css_class("caption")
        self._prev_packages_label.add_css_class("dim-label")
        self._prev_packages_label.set_margin_bottom(8)
        right_box.append(self._prev_packages_label)

        paned.set_end_child(right_box)
        self.append(paned)

        self._populate_bugs()
        self._populate_history()

    def _populate_pick_menu(self) -> None:
        """Populate the Pick menu with packages needing work."""
        self._pick_menu.remove_all()
        data = fetch_and_parse(self._language)
        needs_work = [
            p for p in data
            if p.status in ("untranslated", "fuzzy", "pending-review")
        ]
        for pkg in needs_work[:10]:
            self._pick_menu.append(pkg.package, f"bts.pick-{pkg.package}")

    # -- body template --------------------------------------------------

    def _set_default_body(self) -> None:
        settings = Settings.get()
        name = settings.translator_name or _("Translator Name")
        email = settings.translator_email or "translator@example.com"
        pkg = self._pkg_entry.get_text().strip() if hasattr(self, '_pkg_entry') else "PACKAGE"
        pkg = pkg or "PACKAGE"

        body = (
            f"Package: {pkg}\n"
            f"Severity: wishlist\n"
            f"Tags: l10n patch\n"
            f"\n"
            f"Please find attached the {self._language_name} debconf translation for {pkg}.\n"
            f"\n"
            f"This translation has been reviewed by the {self._language_name} l10n team.\n"
            f"\n"
            f"Translators:\n"
            f"  - {name} <{email}>\n"
        )
        self._body_view.get_buffer().set_text(body)

    def _update_body_template(self) -> None:
        """Update the body when package or settings change."""
        settings = Settings.get()
        name = settings.translator_name or _("Translator Name")
        email = settings.translator_email or "translator@example.com"
        pkg = self._pkg_entry.get_text().strip() or "PACKAGE"
        lang_name = self._lang_name_entry.get_text().strip() or self._language_name

        body = (
            f"Package: {pkg}\n"
            f"Severity: wishlist\n"
            f"Tags: l10n patch\n"
            f"\n"
            f"Please find attached the {lang_name} debconf translation for {pkg}.\n"
            f"\n"
            f"This translation has been reviewed by the {lang_name} l10n team.\n"
            f"\n"
            f"Translators:\n"
            f"  - {name} <{email}>\n"
        )
        self._body_view.get_buffer().set_text(body)

    # -- callbacks ------------------------------------------------------

    def _on_pkg_changed(self, entry: Gtk.Entry) -> None:
        pkg = self._pkg_entry.get_text().strip()
        lang = self._lang_entry.get_text().strip() or self._language
        lang_name = self._lang_name_entry.get_text().strip() or self._language_name
        if pkg:
            self._subject_entry.set_text(
                f"[INTL:{lang}] {lang_name} debconf translation for {pkg}"
            )

    def _on_browse_po(self, btn: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        ff = Gtk.FileFilter()
        ff.set_name(_("PO files"))
        ff.add_pattern("*.po")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(ff)
        dialog.set_filters(filters)
        dialog.open(self._window, None, self._on_po_selected)

    def _on_po_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = dialog.open_finish(result)
            path = gfile.get_path()
            if path:
                self._attach_label.set_label(path)
        except GLib.Error:
            pass

    def _on_preview(self, btn: Gtk.Button) -> None:
        """Open email preview dialog with Edit / Save buttons."""
        report = self._build_report()

        dialog = Adw.Dialog()
        dialog.set_title(_("Email Preview"))
        dialog.set_content_width(650)
        dialog.set_content_height(550)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()

        edit_btn = Gtk.Button(label=_("Edit"))
        edit_btn.connect("clicked", lambda b: dialog.close())
        header.pack_start(edit_btn)

        save_btn = Gtk.Button(label=_("Save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda b: self._on_preview_save(dialog))
        header.pack_end(save_btn)

        toolbar.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        subj_label = Gtk.Label(
            label=_("Subject: %s") % self._subject_entry.get_text(),
            xalign=0,
            wrap=True,
        )
        subj_label.add_css_class("heading")
        content.append(subj_label)

        to_label = Gtk.Label(
            label=_("To: submit@bugs.debian.org"),
            xalign=0,
        )
        to_label.add_css_class("dim-label")
        content.append(to_label)

        content.append(Gtk.Separator())

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

        buf = self._body_view.get_buffer()
        start, end = buf.get_bounds()
        body_text = buf.get_text(start, end, True)
        tv.get_buffer().set_text(body_text)
        scroll.set_child(tv)

        body_frame = Gtk.Frame()
        body_frame.set_child(scroll)
        content.append(body_frame)

        attach = self._attach_label.get_label()
        if attach and attach != _("(none)"):
            att_label = Gtk.Label(
                label=_("Attachment: %s") % attach,
                xalign=0,
            )
            att_label.add_css_class("caption")
            att_label.set_margin_top(4)
            content.append(att_label)

        toolbar.set_content(content)
        dialog.set_child(toolbar)
        dialog.present(self._window)

    def _on_preview_save(self, dialog: Adw.Dialog) -> None:
        pkg = self._pkg_entry.get_text().strip() or "unknown"
        lang = self._lang_entry.get_text().strip() or self._language
        subject = self._subject_entry.get_text()
        report = self._build_report()

        save_dialog = Gtk.FileDialog()
        save_dialog.set_initial_name(f"{pkg}_bug_report.txt")
        save_dialog.save(
            self._window,
            None,
            self._on_report_save_ready,
            (report, dialog, pkg, subject, lang),
        )

    def _on_report_save_ready(
        self,
        file_dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
        user_data: tuple,
    ) -> None:
        report, preview_dialog, pkg, subject, lang = user_data
        try:
            gfile = file_dialog.save_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(report)

        self._submission_log.add(
            package=pkg,
            subject=subject,
            language=lang,
            status="filed",
        )
        self._populate_history()

        preview_dialog.close()
        if self._window:
            self._window.show_toast(_("Bug report saved to %s") % path)

    def _on_copy_report(self, btn: Gtk.Button) -> None:
        report = self._build_report()
        if self._window:
            clipboard = self._window.get_clipboard()
            clipboard.set(report)
            self._window.show_toast(_("Bug report copied to clipboard"))

    def _on_open_mail(self, btn: Gtk.Button) -> None:
        subject = self._subject_entry.get_text()
        buf = self._body_view.get_buffer()
        start, end = buf.get_bounds()
        body = buf.get_text(start, end, True)

        import urllib.parse
        mailto = (
            f"mailto:submit@bugs.debian.org"
            f"?subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}"
        )
        Gtk.show_uri(self._window, mailto, 0)

    def _on_send_smtp(self, btn: Gtk.Button) -> None:
        """Send bug report via SMTP using settings."""
        settings = Settings.get()
        host = settings["smtp_host"]
        if not host:
            if self._window:
                self._window.show_toast(
                    _("SMTP not configured — go to Settings first")
                )
            return

        subject = self._subject_entry.get_text()
        buf = self._body_view.get_buffer()
        start, end = buf.get_bounds()
        body = buf.get_text(start, end, True)
        from_addr = settings.translator_email
        if not from_addr:
            if self._window:
                self._window.show_toast(_("Set your email in Settings first"))
            return

        attach_path = self._attach_label.get_label()
        has_attach = attach_path and attach_path != _("(none)")

        # Build email
        if has_attach:
            msg = MIMEMultipart()
            msg.attach(MIMEText(body, "plain", "utf-8"))
            try:
                with open(attach_path, "rb") as f:
                    att = MIMEApplication(f.read(), Name=Path(attach_path).name)
                att["Content-Disposition"] = (
                    f'attachment; filename="{Path(attach_path).name}"'
                )
                msg.attach(att)
            except OSError as exc:
                if self._window:
                    self._window.show_toast(
                        _("Failed to read attachment: %s") % str(exc)
                    )
                return
        else:
            msg = MIMEText(body, "plain", "utf-8")

        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = "submit@bugs.debian.org"

        # Send
        try:
            port = int(settings["smtp_port"])
            use_tls = settings["smtp_use_tls"]

            if use_tls:
                server = smtplib.SMTP(host, port, timeout=30)
                server.starttls()
            else:
                server = smtplib.SMTP(host, port, timeout=30)

            user = settings["smtp_user"]
            if user:
                # Password would need to be handled securely; for now
                # rely on passwordless/app-password auth
                pass

            server.sendmail(from_addr, ["submit@bugs.debian.org"], msg.as_string())
            server.quit()

            # Log submission
            pkg = self._pkg_entry.get_text().strip() or "unknown"
            lang = self._lang_entry.get_text().strip() or self._language
            self._submission_log.add(
                package=pkg,
                subject=subject,
                language=lang,
                status="sent",
            )
            self._populate_history()

            if self._window:
                self._window.show_toast(_("Bug report sent via SMTP"))

        except Exception as exc:
            if self._window:
                self._window.show_toast(_("SMTP send failed: %s") % str(exc))

    def _build_report(self) -> str:
        subject = self._subject_entry.get_text()
        buf = self._body_view.get_buffer()
        start, end = buf.get_bounds()
        body = buf.get_text(start, end, True)
        attach = self._attach_label.get_label()

        lines = [
            f"To: submit@bugs.debian.org",
            f"Subject: {subject}",
            f"",
            body,
        ]
        if attach and attach != _("(none)"):
            lines.append(f"\n[Attachment: {attach}]")
        return "\n".join(lines)

    # -- filed bugs list ------------------------------------------------

    def _populate_bugs(self) -> None:
        self._apply_bug_filter()

    def _apply_bug_filter(self) -> None:
        query = self._filter_bar.search_text

        while True:
            row = self._bugs_list.get_row_at_index(0)
            if row is None:
                break
            self._bugs_list.remove(row)

        for bug in self._filed_bugs:
            if query and query not in bug["package"].lower() and query not in bug["bug_id"].lower():
                continue
            row = self._make_bug_row(bug)
            self._bugs_list.append(row)

    def _make_bug_row(self, bug: dict[str, str]) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bug_id = Gtk.Label(label=f"#{bug['bug_id']}", xalign=0)
        bug_id.add_css_class("heading")
        bug_id.set_hexpand(True)
        top.append(bug_id)

        badge = StatusBadge(status=bug.get("status", "open"))
        top.append(badge)
        box.append(top)

        subject = Gtk.Label(label=bug["subject"], xalign=0)
        subject.add_css_class("caption")
        subject.set_ellipsize(3)
        box.append(subject)

        info = Gtk.Label(
            label=f"{bug['package']} · {bug.get('date', '')}",
            xalign=0,
        )
        info.add_css_class("caption")
        info.add_css_class("dim-label")
        box.append(info)

        row.set_child(box)
        return row

    # -- submission history -----------------------------------------------

    def _populate_history(self) -> None:
        while True:
            row = self._history_list.get_row_at_index(0)
            if row is None:
                break
            self._history_list.remove(row)

        entries = self._submission_log.entries
        if not entries:
            entries = self._submission_log.get_mock_entries()

        for entry in entries:
            row = self._make_history_row(entry)
            self._history_list.append(row)

        pkgs = self._submission_log.previously_submitted_packages()
        if not pkgs:
            pkgs = [e["package"] for e in self._submission_log.get_mock_entries()]
        if pkgs:
            self._prev_packages_label.set_label(
                _("Previously submitted: %s") % ", ".join(pkgs)
            )
        else:
            self._prev_packages_label.set_label("")

    def _make_history_row(self, entry: dict[str, Any]) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        pkg_label = Gtk.Label(label=entry.get("package", ""), xalign=0)
        pkg_label.add_css_class("heading")
        pkg_label.set_hexpand(True)
        box.append(pkg_label)

        lang_label = Gtk.Label(label=entry.get("language", ""))
        lang_label.add_css_class("caption")
        box.append(lang_label)

        badge = StatusBadge(status=entry.get("status", "filed"))
        box.append(badge)

        ts_label = Gtk.Label(label=entry.get("timestamp", "")[:10])
        ts_label.add_css_class("caption")
        ts_label.add_css_class("dim-label")
        box.append(ts_label)

        row.set_child(box)
        return row


def _get_mock_filed_bugs() -> list[dict[str, str]]:
    return [
        {
            "bug_id": "1045231",
            "package": "locales",
            "subject": "[INTL:sv] Swedish debconf translation for locales",
            "status": "translated",
            "date": "2025-12-01",
        },
        {
            "bug_id": "1048762",
            "package": "tzdata",
            "subject": "[INTL:sv] Swedish debconf translation for tzdata",
            "status": "translated",
            "date": "2025-11-15",
        },
        {
            "bug_id": "1051003",
            "package": "grub-pc",
            "subject": "[INTL:sv] Swedish debconf translation for grub-pc",
            "status": "pending-review",
            "date": "2026-01-10",
        },
        {
            "bug_id": "1052444",
            "package": "dash",
            "subject": "[INTL:sv] Swedish debconf translation for dash",
            "status": "translated",
            "date": "2025-09-05",
        },
        {
            "bug_id": "1053891",
            "package": "popularity-contest",
            "subject": "[INTL:sv] Swedish debconf translation for popularity-contest",
            "status": "pending-review",
            "date": "2026-01-22",
        },
    ]
