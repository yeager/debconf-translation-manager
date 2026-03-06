"""Package List Page — main view showing all untranslated packages."""

from __future__ import annotations

import gettext
import threading
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk, Pango

from debconf_translation_manager.services.l10n_debian import (
    L10nPackageStatus,
    fetch_and_parse,
)
from debconf_translation_manager.services.settings import Settings

if TYPE_CHECKING:
    from debconf_translation_manager.window import MainWindow

_ = gettext.gettext

# Sort modes
SORT_NAME = 0
SORT_PERCENT = 1
SORT_UNTRANSLATED = 2


class PackageListPage(Adw.NavigationPage):
    """Main page: list of packages needing translation."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(title=_("Packages"))
        self._window = window
        self._packages: list[L10nPackageStatus] = []
        self._filtered: list[L10nPackageStatus] = []
        self._sort_mode = SORT_PERCENT
        self._sort_ascending = True
        self._search_text = ""
        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        # Header bar
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label=_("Debconf Translation Manager")))

        # Refresh button
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh package list"))
        refresh_btn.connect("clicked", self._on_refresh)
        header.pack_start(refresh_btn)

        # Stats button
        stats_btn = Gtk.Button(icon_name="org.gnome.Usage-symbolic")
        stats_btn.set_tooltip_text(_("Statistics"))
        stats_btn.connect("clicked", self._on_stats)
        header.pack_end(stats_btn)

        # Preferences button
        prefs_btn = Gtk.Button(icon_name="preferences-system-symbolic")
        prefs_btn.set_tooltip_text(_("Preferences"))
        prefs_btn.connect("clicked", self._on_preferences)
        header.pack_end(prefs_btn)

        toolbar_view.add_top_bar(header)

        # Main content
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Search bar
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search_box.set_margin_start(12)
        search_box.set_margin_end(12)
        search_box.set_margin_top(8)
        search_box.set_margin_bottom(8)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text(_("Filter packages…"))
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("search-changed", self._on_search_changed)
        search_box.append(self._search_entry)

        # Sort dropdown
        sort_model = Gtk.StringList.new([
            _("Sort by Name"),
            _("Sort by Percentage"),
            _("Sort by Untranslated"),
        ])
        self._sort_dropdown = Gtk.DropDown(model=sort_model)
        self._sort_dropdown.set_selected(SORT_PERCENT)
        self._sort_dropdown.connect("notify::selected", self._on_sort_changed)
        search_box.append(self._sort_dropdown)

        main_box.append(search_box)

        # Info bar with stats
        self._info_label = Gtk.Label(xalign=0)
        self._info_label.add_css_class("dim-label")
        self._info_label.add_css_class("caption")
        self._info_label.set_margin_start(16)
        self._info_label.set_margin_bottom(4)
        main_box.append(self._info_label)

        main_box.append(Gtk.Separator())

        # Scrolled list
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(12)
        self._list_box.set_margin_end(12)
        self._list_box.set_margin_top(8)
        self._list_box.set_margin_bottom(8)

        scroll.set_child(self._list_box)

        # Empty state
        self._status_page = Adw.StatusPage()
        self._status_page.set_title(_("Loading Packages"))
        self._status_page.set_description(_("Fetching translation data from debian.org…"))
        self._status_page.set_icon_name("emblem-synchronizing-symbolic")

        self._stack = Gtk.Stack()
        self._stack.add_named(scroll, "list")
        self._stack.add_named(self._status_page, "status")
        self._stack.set_visible_child_name("status")

        main_box.append(self._stack)
        toolbar_view.set_content(main_box)
        self.set_child(toolbar_view)

    def load_data(self) -> None:
        """Start async data fetch."""
        self._status_page.set_title(_("Loading Packages"))
        self._status_page.set_description(_("Fetching translation data from debian.org…"))
        self._status_page.set_icon_name("emblem-synchronizing-symbolic")
        self._stack.set_visible_child_name("status")

        thread = threading.Thread(target=self._fetch_data, daemon=True)
        thread.start()

    def _fetch_data(self) -> None:
        lang = Settings.get().language_code
        results = fetch_and_parse(lang)
        GLib.idle_add(self._on_data_loaded, results)

    def _on_data_loaded(self, results: list[L10nPackageStatus]) -> bool:
        # Filter out 100% translated packages
        self._packages = [p for p in results if p.score < 100]

        if not self._packages:
            self._status_page.set_title(_("No Packages Found"))
            self._status_page.set_description(
                _("All packages are fully translated, or data could not be fetched.")
            )
            self._status_page.set_icon_name("emblem-ok-symbolic")
            self._stack.set_visible_child_name("status")
        else:
            self._apply_filter_and_sort()
            self._stack.set_visible_child_name("list")

        return False

    def _apply_filter_and_sort(self) -> None:
        query = self._search_text.lower()
        self._filtered = [
            p for p in self._packages
            if not query or query in p.package.lower()
        ]

        # Sort
        if self._sort_mode == SORT_NAME:
            self._filtered.sort(key=lambda p: p.package)
        elif self._sort_mode == SORT_PERCENT:
            self._filtered.sort(key=lambda p: p.score)
        elif self._sort_mode == SORT_UNTRANSLATED:
            self._filtered.sort(key=lambda p: p.untranslated, reverse=True)

        self._rebuild_list()

    def _rebuild_list(self) -> None:
        # Clear
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        total = len(self._packages)
        shown = len(self._filtered)
        lang = Settings.get().language_code
        self._info_label.set_label(
            _("%(shown)d of %(total)d packages needing translation (%(lang)s)")
            % {"shown": shown, "total": total, "lang": lang}
        )

        for pkg in self._filtered:
            row = self._make_row(pkg)
            self._list_box.append(row)

    def _make_row(self, pkg: L10nPackageStatus) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_activatable(True)

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)

        # Color indicator
        color_box = Gtk.Box()
        color_box.set_size_request(4, -1)
        if pkg.score < 50:
            color_box.add_css_class("error")
        elif pkg.score < 90:
            color_box.add_css_class("warning")
        else:
            color_box.add_css_class("success")
        main_box.append(color_box)

        # Package info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)

        name_label = Gtk.Label(label=pkg.package, xalign=0)
        name_label.add_css_class("heading")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        info_box.append(name_label)

        detail_text = _("%(translated)d/%(total)d translated, %(untranslated)d untranslated") % {
            "translated": pkg.translated,
            "total": pkg.total,
            "untranslated": pkg.untranslated,
        }
        if pkg.fuzzy > 0:
            detail_text += _(", %(fuzzy)d fuzzy") % {"fuzzy": pkg.fuzzy}

        detail_label = Gtk.Label(label=detail_text, xalign=0)
        detail_label.add_css_class("dim-label")
        detail_label.add_css_class("caption")
        info_box.append(detail_label)

        main_box.append(info_box)

        # Percentage badge
        pct_label = Gtk.Label(label=f"{pkg.score}%")
        pct_label.add_css_class("heading")
        if pkg.score < 50:
            pct_label.add_css_class("error")
        elif pkg.score < 90:
            pct_label.add_css_class("warning")
        else:
            pct_label.add_css_class("success")
        main_box.append(pct_label)

        # Arrow
        arrow = Gtk.Image.new_from_icon_name("go-next-symbolic")
        arrow.add_css_class("dim-label")
        main_box.append(arrow)

        row.set_child(main_box)

        # Click handler via gesture
        gesture = Gtk.GestureClick()
        gesture.connect("released", lambda g, n, x, y: self._on_package_clicked(pkg))
        row.add_controller(gesture)

        return row

    def _on_package_clicked(self, pkg: L10nPackageStatus) -> None:
        self._window.show_package_detail(pkg)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._search_text = entry.get_text()
        self._apply_filter_and_sort()

    def _on_sort_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        self._sort_mode = dropdown.get_selected()
        self._apply_filter_and_sort()

    def _on_refresh(self, btn: Gtk.Button) -> None:
        self.load_data()

    def _on_stats(self, btn: Gtk.Button) -> None:
        self._window.show_stats()

    def _on_preferences(self, btn: Gtk.Button) -> None:
        self._window.show_preferences()
