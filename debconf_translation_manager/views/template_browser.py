"""Template Browser view — browse packages needing debconf translations."""

from __future__ import annotations

import gettext
import threading
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from debconf_translation_manager.services.l10n_debian import (
    L10nPackageStatus,
    fetch_and_parse,
    get_mock_l10n_data,
)
from debconf_translation_manager.services.settings import Settings
from debconf_translation_manager.widgets.filter_bar import FilterBar
from debconf_translation_manager.widgets.status_badge import StatusBadge

_ = gettext.gettext


class TemplateBrowserView(Gtk.Box):
    """Browse packages needing debconf translation from l10n.debian.org."""

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._packages: list[L10nPackageStatus] = get_mock_l10n_data(
            Settings.get().language_code
        )
        self._filtered: list[L10nPackageStatus] = list(self._packages)
        self._is_real_data = False
        self._build_ui()
        self._populate()

    def focus_search(self) -> None:
        self._filter_bar.focus_search()

    def get_export_data(self) -> list[dict[str, Any]]:
        return [
            {
                "package": p.package,
                "status": p.status,
                "score": p.score,
                "translator": p.translator,
                "date": p.date,
            }
            for p in self._filtered
        ]

    def _build_ui(self) -> None:
        # Title row
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.set_margin_start(16)
        title_box.set_margin_end(16)
        title_box.set_margin_top(12)
        title_box.set_margin_bottom(4)
        title = Gtk.Label(label=_("Package Browser"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title_box.append(title)

        self._count_label = Gtk.Label()
        self._count_label.add_css_class("dim-label")
        self._count_label.set_halign(Gtk.Align.START)
        self._count_label.set_hexpand(True)
        title_box.append(self._count_label)

        # Fetch button
        self._fetch_btn = Gtk.Button(label=_("Fetch Packages"))
        self._fetch_btn.set_icon_name("emblem-synchronizing-symbolic")
        self._fetch_btn.add_css_class("suggested-action")
        self._fetch_btn.connect("clicked", self._on_fetch_packages)
        title_box.append(self._fetch_btn)

        self.append(title_box)

        # Data source indicator
        self._source_label = Gtk.Label(
            label=_("Showing mock data — click Fetch to load from l10n.debian.org"),
            xalign=0,
        )
        self._source_label.add_css_class("dim-label")
        self._source_label.add_css_class("caption")
        self._source_label.set_margin_start(16)
        self._source_label.set_margin_bottom(4)
        self.append(self._source_label)

        # Filter bar
        status_options = [
            "All Statuses", "untranslated", "fuzzy", "translated",
            "pending-review", "in-progress", "filed",
        ]

        self._filter_bar = FilterBar(
            search_placeholder=_("Search packages…"),
            filters=[
                (_("Status"), status_options),
            ],
            on_changed=self._apply_filters,
        )
        self.append(self._filter_bar)
        self.append(Gtk.Separator())

        # Package list
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(16)
        self._list_box.set_margin_end(16)
        self._list_box.set_margin_top(8)
        self._list_box.set_margin_bottom(8)
        self._list_box.connect("row-selected", self._on_row_selected)

        scroll.set_child(self._list_box)
        self.append(scroll)

        # Detail panel at bottom
        self._detail_revealer = Gtk.Revealer()
        self._detail_revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_UP
        )
        self._detail_box = self._build_detail_panel()
        self._detail_revealer.set_child(self._detail_box)
        self.append(self._detail_revealer)

    def _build_detail_panel(self) -> Gtk.Box:
        frame = Gtk.Frame()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        self._detail_title = Gtk.Label(xalign=0)
        self._detail_title.add_css_class("title-4")
        box.append(self._detail_title)

        self._detail_info = Gtk.Label(xalign=0, wrap=True)
        self._detail_info.add_css_class("dim-label")
        box.append(self._detail_info)

        # Action buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(4)

        self._download_btn = Gtk.Button(label=_("Download & Edit PO"))
        self._download_btn.add_css_class("suggested-action")
        self._download_btn.connect("clicked", self._on_download_and_edit)
        btn_row.append(self._download_btn)

        self._bts_btn = Gtk.Button(label=_("File Bug for Package"))
        self._bts_btn.connect("clicked", self._on_file_bug)
        btn_row.append(self._bts_btn)

        box.append(btn_row)

        frame.set_child(box)
        return frame

    def _populate(self) -> None:
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = self._filter_bar.search_text
        status_filter = self._filter_bar.get_filter_value(_("Status"))

        self._filtered = []
        for p in self._packages:
            if query and query not in p.package.lower() and query not in p.translator.lower():
                continue
            if status_filter and not status_filter.startswith("All") and p.status != status_filter:
                continue
            self._filtered.append(p)

        self._rebuild_list()

    def _rebuild_list(self) -> None:
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        for p in self._filtered:
            row = self._make_package_row(p)
            self._list_box.append(row)

        self._count_label.set_label(f"({len(self._filtered)})")
        self._detail_revealer.set_reveal_child(False)

    def _make_package_row(self, p: L10nPackageStatus) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._pkg = p

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        # Left: package name + translator
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)

        name = Gtk.Label(label=p.package, xalign=0)
        name.add_css_class("heading")
        name.set_ellipsize(3)
        left.append(name)

        if p.translator:
            translator_lbl = Gtk.Label(label=p.translator, xalign=0)
            translator_lbl.add_css_class("dim-label")
            translator_lbl.set_ellipsize(3)
            left.append(translator_lbl)

        box.append(left)

        # Middle: score
        if p.score > 0:
            score_lbl = Gtk.Label(label=f"{p.score}%")
            score_lbl.add_css_class("caption")
            if p.score == 100:
                score_lbl.add_css_class("success")
            elif p.score >= 50:
                score_lbl.add_css_class("accent")
            else:
                score_lbl.add_css_class("warning")
            box.append(score_lbl)

        # Right: status badge
        badge = StatusBadge(status=p.status)
        box.append(badge)

        row.set_child(box)
        return row

    def _on_row_selected(
        self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None
    ) -> None:
        if row is None:
            self._detail_revealer.set_reveal_child(False)
            return

        p: L10nPackageStatus = row._pkg
        self._detail_title.set_label(p.package)

        parts = [f"{_('Status')}: {p.status}"]
        if p.score:
            parts.append(f"{_('Score')}: {p.score}%")
        if p.translated or p.fuzzy or p.untranslated:
            parts.append(f"T:{p.translated} F:{p.fuzzy} U:{p.untranslated}")
        if p.translator:
            parts.append(f"{_('Translator')}: {p.translator}")
        if p.date:
            parts.append(f"{_('Date')}: {p.date}")
        if p.bug_number:
            parts.append(f"Bug: #{p.bug_number}")

        self._detail_info.set_label("  |  ".join(parts))

        # Enable/disable download button based on po_url
        has_po = bool(p.po_url)
        self._download_btn.set_sensitive(has_po or p.status == "untranslated")
        if has_po:
            self._download_btn.set_label(_("Download & Edit PO"))
        elif p.status == "untranslated":
            self._download_btn.set_label(_("Open PO Editor"))
        else:
            self._download_btn.set_label(_("No PO available"))

        self._detail_revealer.set_reveal_child(True)

    # ── Fetch real data ────────────────────────────────────────────────

    def _on_fetch_packages(self, btn: Gtk.Button) -> None:
        """Fetch real package data from l10n.debian.org in a background thread."""
        lang = Settings.get().language_code
        self._fetch_btn.set_sensitive(False)
        self._fetch_btn.set_label(_("Fetching…"))

        def _do_fetch() -> list[L10nPackageStatus]:
            return fetch_and_parse(lang)

        def _on_done(results: list[L10nPackageStatus]) -> None:
            self._packages = results
            self._is_real_data = len(results) > 0
            self._source_label.set_label(
                _("Showing %d packages from l10n.debian.org") % len(results)
                if self._is_real_data
                else _("Using mock data (fetch failed)")
            )
            self._apply_filters()
            self._fetch_btn.set_sensitive(True)
            self._fetch_btn.set_label(_("Fetch Packages"))
            if self._window:
                self._window.show_toast(
                    _("Loaded %d packages") % len(results)
                )

        def _thread_target() -> None:
            results = _do_fetch()
            GLib.idle_add(_on_done, results)

        threading.Thread(target=_thread_target, daemon=True).start()

    # ── Actions ────────────────────────────────────────────────────────

    def _on_download_and_edit(self, btn: Gtk.Button) -> None:
        """Download PO for selected package and open in PO editor."""
        row = self._list_box.get_selected_row()
        if row is None:
            return

        p: L10nPackageStatus = row._pkg

        if p.po_url:
            self._download_and_open_po(p)
        else:
            # No .po available — just switch to editor
            if self._window:
                self._window.navigate_to_editor(package=p.package)

    def _download_and_open_po(self, p: L10nPackageStatus) -> None:
        """Download .po file in background thread, then open in editor."""
        from debconf_translation_manager.services.l10n_debian import download_po_file

        self._download_btn.set_sensitive(False)
        self._download_btn.set_label(_("Downloading…"))

        def _do_download() -> str | None:
            return download_po_file(p.po_url)

        def _on_done(path: str | None) -> None:
            self._download_btn.set_sensitive(True)
            self._download_btn.set_label(_("Download & Edit PO"))
            if path and self._window:
                self._window.navigate_to_editor(
                    package=p.package, po_file_path=path
                )
                self._window.show_toast(
                    _("Downloaded PO for %s") % p.package
                )
            elif self._window:
                self._window.show_toast(_("Download failed"))

        def _thread_target() -> None:
            path = _do_download()
            GLib.idle_add(_on_done, path)

        threading.Thread(target=_thread_target, daemon=True).start()

    def _on_file_bug(self, btn: Gtk.Button) -> None:
        """Navigate to BTS workflow with package pre-filled."""
        row = self._list_box.get_selected_row()
        if row is None:
            return

        p: L10nPackageStatus = row._pkg
        if self._window:
            self._window.navigate_to_bts(package=p.package)
