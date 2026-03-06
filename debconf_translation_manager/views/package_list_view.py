"""Package List View — main content showing all packages needing translation."""

from __future__ import annotations

import gettext
import subprocess
import threading
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk, Pango

from debconf_translation_manager.services.l10n_debian import (
    L10nPackageStatus,
    download_po_file,
    fetch_and_parse,
)
from debconf_translation_manager.services.settings import Settings

if TYPE_CHECKING:
    from debconf_translation_manager.window import MainWindow

_ = gettext.gettext

SORT_NAME = 0
SORT_PERCENT = 1
SORT_UNTRANSLATED = 2


class PackageListView(Gtk.Box):
    """Package list content panel."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window
        self._packages: list[L10nPackageStatus] = []
        self._filtered: list[L10nPackageStatus] = []
        self._sort_mode = SORT_PERCENT
        self._search_text = ""
        self._selected_pkg: L10nPackageStatus | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        # Header bar
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label=_("Packages")))

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh package list"))
        refresh_btn.connect("clicked", self._on_refresh)
        header.pack_start(refresh_btn)

        # Sync TX button
        sync_btn = Gtk.Button(icon_name="emblem-synchronizing-symbolic")
        sync_btn.set_tooltip_text(_("Sync TX (tx push -s)"))
        sync_btn.connect("clicked", self._on_sync_tx)
        header.pack_end(sync_btn)

        # Download PO button
        download_btn = Gtk.Button(icon_name="folder-download-symbolic")
        download_btn.set_tooltip_text(_("Download PO for selected package"))
        download_btn.connect("clicked", self._on_download_po)
        header.pack_end(download_btn)

        self.append(header)

        # Search + filter bar
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

        sort_model = Gtk.StringList.new([
            _("Sort by Name"),
            _("Sort by Percentage"),
            _("Sort by Untranslated"),
        ])
        self._sort_dropdown = Gtk.DropDown(model=sort_model)
        self._sort_dropdown.set_selected(SORT_PERCENT)
        self._sort_dropdown.connect("notify::selected", self._on_sort_changed)
        search_box.append(self._sort_dropdown)

        self.append(search_box)

        # Info label
        self._info_label = Gtk.Label(xalign=0)
        self._info_label.add_css_class("dim-label")
        self._info_label.add_css_class("caption")
        self._info_label.set_margin_start(16)
        self._info_label.set_margin_bottom(4)
        self.append(self._info_label)

        self.append(Gtk.Separator())

        # Stack: list vs status
        self._stack = Gtk.Stack()

        # List view
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(12)
        self._list_box.set_margin_end(12)
        self._list_box.set_margin_top(8)
        self._list_box.set_margin_bottom(8)
        self._list_box.connect("row-selected", self._on_row_selected)

        scroll.set_child(self._list_box)
        self._stack.add_named(scroll, "list")

        # Status page (loading/empty)
        self._status_page = Adw.StatusPage()
        self._status_page.set_title(_("Loading Packages"))
        self._status_page.set_description(_("Fetching translation data from debian.org…"))
        self._status_page.set_icon_name("emblem-synchronizing-symbolic")
        self._stack.add_named(self._status_page, "status")
        self._stack.set_visible_child_name("status")

        self.append(self._stack)

    def load_data(self) -> None:
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
        if self._sort_mode == SORT_NAME:
            self._filtered.sort(key=lambda p: p.package)
        elif self._sort_mode == SORT_PERCENT:
            self._filtered.sort(key=lambda p: p.score)
        elif self._sort_mode == SORT_UNTRANSLATED:
            self._filtered.sort(key=lambda p: p.untranslated, reverse=True)
        self._rebuild_list()

    def _rebuild_list(self) -> None:
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
        row._pkg = pkg  # store reference

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

        row.set_child(main_box)
        return row

    def _on_row_selected(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is not None and hasattr(row, '_pkg'):
            self._selected_pkg = row._pkg

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._search_text = entry.get_text()
        self._apply_filter_and_sort()

    def _on_sort_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        self._sort_mode = dropdown.get_selected()
        self._apply_filter_and_sort()

    def _on_refresh(self, btn: Gtk.Button) -> None:
        self.load_data()

    def _on_sync_tx(self, btn: Gtk.Button) -> None:
        """Sync with Transifex: push sources and pull translations."""
        self._window.show_toast(_("Syncing with Transifex…"))
        btn.set_sensitive(False)  # Disable button during sync
        thread = threading.Thread(target=self._do_sync_tx, args=(btn,), daemon=True)
        thread.start()

    def _do_sync_tx(self, btn: Gtk.Button) -> None:
        """Run TX sync commands in background."""
        try:
            # First push sources
            GLib.idle_add(self._window.show_toast, _("Pushing source strings…"))
            push_result = subprocess.run(
                ["tx", "push", "-s"],
                capture_output=True, text=True, timeout=120
            )
            
            if push_result.returncode != 0:
                error_msg = push_result.stderr or _("Push failed")
                GLib.idle_add(self._window.show_toast, f"TX push error: {error_msg[:150]}")
                return
            
            # Then pull translations
            from debconf_translation_manager.services.settings import Settings
            lang_code = Settings.get().language_code
            
            GLib.idle_add(self._window.show_toast, _(f"Pulling {lang_code} translations…"))
            pull_result = subprocess.run(
                ["tx", "pull", "-l", lang_code, "--minimum-perc", "20"],
                capture_output=True, text=True, timeout=180
            )
            
            if pull_result.returncode == 0:
                GLib.idle_add(self._window.show_toast, _("TX sync completed successfully"))
            else:
                error_msg = pull_result.stderr or _("Pull failed")
                GLib.idle_add(self._window.show_toast, f"TX pull error: {error_msg[:150]}")
                
        except FileNotFoundError:
            GLib.idle_add(self._window.show_toast, _("tx CLI not found. Install transifex-client."))
        except subprocess.TimeoutExpired:
            GLib.idle_add(self._window.show_toast, _("TX sync timed out"))
        except Exception as exc:
            GLib.idle_add(self._window.show_toast, f"TX sync error: {str(exc)[:150]}")
        finally:
            # Re-enable button
            GLib.idle_add(btn.set_sensitive, True)

    def _on_download_po(self, btn: Gtk.Button) -> None:
        """Download PO file for selected package and open in editor."""
        pkg = self._selected_pkg
        if pkg is None:
            self._window.show_toast(_("Select a package first"))
            return
        if not pkg.po_url:
            self._window.show_toast(_("No PO download URL available for this package"))
            return

        self._window.show_toast(_("Downloading PO file for %s…") % pkg.package)
        thread = threading.Thread(target=self._do_download, args=(pkg,), daemon=True)
        thread.start()

    def _do_download(self, pkg: L10nPackageStatus) -> None:
        cache_dir = str(Settings.get().cache_dir / "po_files")
        path = download_po_file(pkg.po_url, cache_dir)
        if path:
            GLib.idle_add(self._on_download_done, path, pkg)
        else:
            GLib.idle_add(self._window.show_toast, _("Download failed"))

    def _on_download_done(self, path: str, pkg: L10nPackageStatus) -> bool:
        self._window.show_toast(_("Downloaded: %s") % path)
        self._window.open_po_in_editor(path, pkg)
        return False
