"""DDTSS Workflow view — submit translations, review queue, approve/reject
via ddtp.debian.org."""

from __future__ import annotations

import gettext
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from debconf_translation_manager.services.ddtss import (
    DDTSSEntry,
    get_mock_ddtss_data,
    fetch_open_translations,
    submit_translation,
)
from debconf_translation_manager.widgets.filter_bar import FilterBar
from debconf_translation_manager.widgets.status_badge import StatusBadge

_ = gettext.gettext


class DDTSSWorkflowView(Gtk.Box):
    """DDTSS submit/review workflow.

    Features:
    - View open translations needing work
    - Submit new translations
    - Review queue with approve/reject
    - Login placeholder (DDTSS auth)
    """

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._language = "sv"
        self._entries: list[DDTSSEntry] = get_mock_ddtss_data(self._language)
        self._filtered: list[DDTSSEntry] = list(self._entries)
        self._logged_in = False
        self._build_ui()
        self._apply_filters()

    def focus_search(self) -> None:
        self._filter_bar.focus_search()

    def get_export_data(self) -> list[dict[str, Any]]:
        return [
            {
                "package": e.package,
                "original": e.original,
                "translation": e.translation,
                "status": e.status,
                "reviewer_count": e.reviewer_count,
            }
            for e in self._filtered
        ]

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        # Title row
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_row.set_margin_start(16)
        title_row.set_margin_end(16)
        title_row.set_margin_top(12)
        title_row.set_margin_bottom(4)

        title = Gtk.Label(label=_("DDTSS Workflow"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        title_row.append(title)

        # Login/status
        self._login_btn = Gtk.Button(label=_("Login to DDTSS"))
        self._login_btn.connect("clicked", self._on_login)
        title_row.append(self._login_btn)

        self._status_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        title_row.append(self._status_icon)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh from ddtp.debian.org"))
        refresh_btn.connect("clicked", self._on_refresh)
        title_row.append(refresh_btn)

        self.append(title_row)

        # Info bar
        info = Gtk.Label(
            label=_("Source: https://ddtp.debian.org — Debian Description Translation Project"),
            xalign=0,
        )
        info.add_css_class("caption")
        info.add_css_class("dim-label")
        info.set_margin_start(16)
        info.set_selectable(True)
        self.append(info)

        # Filter bar
        self._filter_bar = FilterBar(
            search_placeholder=_("Filter packages…"),
            filters=[
                (_("Status"), ["All", "open", "reviewed", "accepted"]),
            ],
            on_changed=self._apply_filters,
        )
        self.append(self._filter_bar)

        # Summary
        summary = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        summary.set_margin_start(16)
        summary.set_margin_end(16)
        summary.set_margin_top(4)
        summary.set_margin_bottom(4)

        self._sum_open = Gtk.Label()
        self._sum_open.add_css_class("caption")
        summary.append(self._sum_open)

        self._sum_reviewed = Gtk.Label()
        self._sum_reviewed.add_css_class("caption")
        self._sum_reviewed.add_css_class("success")
        summary.append(self._sum_reviewed)

        self._sum_accepted = Gtk.Label()
        self._sum_accepted.add_css_class("caption")
        self._sum_accepted.add_css_class("accent")
        summary.append(self._sum_accepted)
        self.append(summary)

        self.append(Gtk.Separator())

        # Paned: entry list + editor/review panel
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(400)

        # Left: entry list
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_size_request(280, -1)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(8)
        self._list_box.set_margin_end(4)
        self._list_box.set_margin_top(8)
        self._list_box.set_margin_bottom(8)
        self._list_box.connect("row-selected", self._on_entry_selected)
        list_scroll.set_child(self._list_box)
        paned.set_start_child(list_scroll)

        # Right: translate/review panel
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_box.set_margin_start(8)
        right_box.set_margin_end(16)
        right_box.set_margin_top(8)
        right_box.set_margin_bottom(8)

        # Original description
        orig_label = Gtk.Label(label=_("Original (English)"), xalign=0)
        orig_label.add_css_class("heading")
        right_box.append(orig_label)

        orig_scroll = Gtk.ScrolledWindow()
        orig_scroll.set_min_content_height(80)
        orig_scroll.set_vexpand(True)

        self._orig_view = Gtk.TextView()
        self._orig_view.set_editable(False)
        self._orig_view.set_cursor_visible(False)
        self._orig_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._orig_view.set_left_margin(8)
        self._orig_view.set_right_margin(8)
        self._orig_view.set_top_margin(4)
        self._orig_view.set_bottom_margin(4)
        self._orig_view.add_css_class("monospace")
        orig_scroll.set_child(self._orig_view)

        orig_frame = Gtk.Frame()
        orig_frame.set_child(orig_scroll)
        right_box.append(orig_frame)

        # Translation
        trans_label = Gtk.Label(label=_("Translation"), xalign=0)
        trans_label.add_css_class("heading")
        right_box.append(trans_label)

        trans_scroll = Gtk.ScrolledWindow()
        trans_scroll.set_min_content_height(80)
        trans_scroll.set_vexpand(True)

        self._trans_view = Gtk.TextView()
        self._trans_view.set_editable(True)
        self._trans_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._trans_view.set_left_margin(8)
        self._trans_view.set_right_margin(8)
        self._trans_view.set_top_margin(4)
        self._trans_view.set_bottom_margin(4)
        self._trans_view.add_css_class("monospace")
        trans_scroll.set_child(self._trans_view)

        trans_frame = Gtk.Frame()
        trans_frame.set_child(trans_scroll)
        right_box.append(trans_frame)

        # Review info
        self._review_info = Gtk.Label(xalign=0)
        self._review_info.add_css_class("caption")
        self._review_info.add_css_class("dim-label")
        right_box.append(self._review_info)

        # Action buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(4)

        self._submit_btn = Gtk.Button(label=_("Submit Translation"))
        self._submit_btn.add_css_class("suggested-action")
        self._submit_btn.connect("clicked", self._on_submit)
        btn_row.append(self._submit_btn)

        self._approve_btn = Gtk.Button(label=_("Approve"))
        self._approve_btn.add_css_class("success")
        self._approve_btn.connect("clicked", self._on_approve)
        btn_row.append(self._approve_btn)

        self._reject_btn = Gtk.Button(label=_("Reject"))
        self._reject_btn.add_css_class("destructive-action")
        self._reject_btn.connect("clicked", self._on_reject)
        btn_row.append(self._reject_btn)

        self._copy_btn = Gtk.Button(label=_("Copy Original"))
        self._copy_btn.connect("clicked", self._on_copy_original)
        btn_row.append(self._copy_btn)

        right_box.append(btn_row)

        # Placeholder
        self._placeholder = Adw.StatusPage()
        self._placeholder.set_icon_name("document-edit-symbolic")
        self._placeholder.set_title(_("Select a package"))
        self._placeholder.set_description(
            _("Choose a package to translate or review its description.")
        )
        self._placeholder.set_vexpand(True)

        self._detail_stack = Gtk.Stack()
        self._detail_stack.add_named(self._placeholder, "placeholder")
        self._detail_stack.add_named(right_box, "editor")
        self._detail_stack.set_visible_child_name("placeholder")

        paned.set_end_child(self._detail_stack)
        self.append(paned)

    # -- data -----------------------------------------------------------

    def _apply_filters(self) -> None:
        query = self._filter_bar.search_text
        status_filter = self._filter_bar.get_filter_value(_("Status"))

        self._filtered = []
        for e in self._entries:
            if query and query not in e.package.lower():
                continue
            if status_filter and status_filter != "All" and e.status != status_filter:
                continue
            self._filtered.append(e)

        # Update summary
        open_count = sum(1 for e in self._entries if e.status == "open")
        reviewed = sum(1 for e in self._entries if e.status == "reviewed")
        accepted = sum(1 for e in self._entries if e.status == "accepted")
        self._sum_open.set_label(_("Open: %d") % open_count)
        self._sum_reviewed.set_label(_("Reviewed: %d") % reviewed)
        self._sum_accepted.set_label(_("Accepted: %d") % accepted)

        self._rebuild_list()

    def _rebuild_list(self) -> None:
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        for entry in self._filtered:
            row = self._make_entry_row(entry)
            self._list_box.append(row)

        self._detail_stack.set_visible_child_name("placeholder")

    def _make_entry_row(self, entry: DDTSSEntry) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._entry = entry

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)

        name = Gtk.Label(label=entry.package, xalign=0)
        name.add_css_class("heading")
        left.append(name)

        preview = entry.original[:60] + ("…" if len(entry.original) > 60 else "")
        desc = Gtk.Label(label=preview, xalign=0)
        desc.add_css_class("caption")
        desc.add_css_class("dim-label")
        desc.set_ellipsize(3)
        left.append(desc)

        box.append(left)

        # Reviewer count
        if entry.reviewer_count > 0:
            reviews = Gtk.Label(label=f"{entry.reviewer_count}R")
            reviews.add_css_class("caption")
            box.append(reviews)

        badge = StatusBadge(status=entry.status)
        box.append(badge)

        row.set_child(box)
        return row

    # -- callbacks ------------------------------------------------------

    def _on_entry_selected(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            self._detail_stack.set_visible_child_name("placeholder")
            return

        entry = row._entry
        self._orig_view.get_buffer().set_text(entry.original)
        self._trans_view.get_buffer().set_text(entry.translation)
        self._review_info.set_label(
            f"{_('Status')}: {entry.status} · "
            f"{_('Reviews')}: {entry.reviewer_count} · "
            f"MD5: {entry.description_md5}"
        )

        # Show/hide buttons based on status
        self._submit_btn.set_visible(entry.status == "open" and not entry.translation)
        self._approve_btn.set_visible(entry.status in ("open", "reviewed") and entry.translation)
        self._reject_btn.set_visible(entry.status in ("open", "reviewed") and entry.translation)

        self._detail_stack.set_visible_child_name("editor")

    def _on_login(self, btn: Gtk.Button) -> None:
        if self._logged_in:
            self._logged_in = False
            self._login_btn.set_label(_("Login to DDTSS"))
            self._status_icon.set_from_icon_name("dialog-error-symbolic")
            if self._window:
                self._window.show_toast(_("Logged out"))
        else:
            # Show login dialog
            self._show_login_dialog()

    def _show_login_dialog(self) -> None:
        dialog = Adw.Dialog()
        dialog.set_title(_("DDTSS Login"))
        dialog.set_content_width(400)
        dialog.set_content_height(280)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        info = Gtk.Label(
            label=_("Enter your DDTSS credentials to submit and review translations."),
            wrap=True,
        )
        box.append(info)

        user_entry = Gtk.Entry()
        user_entry.set_placeholder_text(_("Username / Email"))
        box.append(user_entry)

        pass_entry = Gtk.PasswordEntry()
        pass_entry.set_show_peek_icon(True)
        box.append(pass_entry)

        login_btn = Gtk.Button(label=_("Login"))
        login_btn.add_css_class("suggested-action")

        def do_login(b):
            self._logged_in = True
            self._login_btn.set_label(_("Logout"))
            self._status_icon.set_from_icon_name("emblem-ok-symbolic")
            dialog.close()
            if self._window:
                self._window.show_toast(_("Logged in to DDTSS (simulated)"))

        login_btn.connect("clicked", do_login)
        box.append(login_btn)

        toolbar.set_content(box)
        dialog.set_child(toolbar)
        dialog.present(self._window)

    def _on_refresh(self, btn: Gtk.Button) -> None:
        self._entries = get_mock_ddtss_data(self._language)
        self._apply_filters()
        if self._window:
            self._window.show_toast(_("Refreshed DDTSS data"))

    def _on_submit(self, btn: Gtk.Button) -> None:
        buf = self._trans_view.get_buffer()
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, True)
        if not text.strip():
            if self._window:
                self._window.show_toast(_("Translation is empty"))
            return

        row = self._list_box.get_selected_row()
        if row is not None:
            entry = row._entry
            success = submit_translation(entry, text)
            if success:
                entry.translation = text
                entry.status = "reviewed"
                self._apply_filters()
                if self._window:
                    self._window.show_toast(
                        _("Translation submitted for %s") % entry.package
                    )

    def _on_approve(self, btn: Gtk.Button) -> None:
        row = self._list_box.get_selected_row()
        if row is not None:
            entry = row._entry
            entry.reviewer_count += 1
            if entry.reviewer_count >= 2:
                entry.status = "accepted"
            else:
                entry.status = "reviewed"
            self._apply_filters()
            if self._window:
                self._window.show_toast(_("Approved: %s") % entry.package)

    def _on_reject(self, btn: Gtk.Button) -> None:
        row = self._list_box.get_selected_row()
        if row is not None:
            entry = row._entry
            entry.status = "open"
            entry.reviewer_count = 0
            self._apply_filters()
            if self._window:
                self._window.show_toast(_("Rejected: %s") % entry.package)

    def _on_copy_original(self, btn: Gtk.Button) -> None:
        buf = self._orig_view.get_buffer()
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, True)
        self._trans_view.get_buffer().set_text(text)
