"""PO Editor Page — built-in translation editor for PO files."""

from __future__ import annotations

import gettext
from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from debconf_translation_manager.services.l10n_debian import L10nPackageStatus
from debconf_translation_manager.services.settings import Settings

if TYPE_CHECKING:
    from debconf_translation_manager.window import MainWindow

_ = gettext.gettext

try:
    import polib
except ImportError:
    polib = None


class PoEditorPage(Adw.NavigationPage):
    """Side-by-side PO file editor with fuzzy/untranslated highlighting."""

    def __init__(
        self, window: MainWindow, po_path: str, pkg: L10nPackageStatus
    ) -> None:
        super().__init__(title=_("Translate: %s") % pkg.package)
        self._window = window
        self._po_path = po_path
        self._pkg = pkg
        self._po_file = None
        self._entries: list = []
        self._filtered: list = []
        self._current_idx: int = -1
        self._search_text = ""
        self._filter_mode = "all"  # all, untranslated, fuzzy
        self._build_ui()
        self._load_file()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        # Header
        header = Adw.HeaderBar()

        save_btn = Gtk.Button(icon_name="document-save-symbolic")
        save_btn.set_tooltip_text(_("Save (Ctrl+S)"))
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        submit_btn = Gtk.Button(label=_("Submit"))
        submit_btn.add_css_class("suggested-action")
        submit_btn.connect("clicked", self._on_submit)
        header.pack_end(submit_btn)

        toolbar_view.add_top_bar(header)

        # Main content: paned view
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Search + filter bar
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        filter_box.set_margin_start(8)
        filter_box.set_margin_end(8)
        filter_box.set_margin_top(6)
        filter_box.set_margin_bottom(6)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text(_("Search strings…"))
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("search-changed", self._on_search_changed)
        filter_box.append(self._search_entry)

        filter_model = Gtk.StringList.new([
            _("All"),
            _("Untranslated"),
            _("Fuzzy"),
            _("Translated"),
        ])
        self._filter_dropdown = Gtk.DropDown(model=filter_model)
        self._filter_dropdown.set_selected(0)
        self._filter_dropdown.connect("notify::selected", self._on_filter_changed)
        filter_box.append(self._filter_dropdown)

        main_box.append(filter_box)

        # Status bar
        self._status_label = Gtk.Label(xalign=0)
        self._status_label.add_css_class("dim-label")
        self._status_label.add_css_class("caption")
        self._status_label.set_margin_start(12)
        self._status_label.set_margin_bottom(4)
        main_box.append(self._status_label)

        main_box.append(Gtk.Separator())

        # Paned: list on left, editor on right
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(400)

        # Left: entry list
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_size_request(280, -1)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(4)
        self._list_box.set_margin_end(4)
        self._list_box.set_margin_top(4)
        self._list_box.set_margin_bottom(4)
        self._list_box.connect("row-selected", self._on_entry_selected)
        list_scroll.set_child(self._list_box)
        paned.set_start_child(list_scroll)

        # Right: editor
        editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        editor_box.set_margin_start(8)
        editor_box.set_margin_end(8)
        editor_box.set_margin_top(8)
        editor_box.set_margin_bottom(8)

        # Source (msgid)
        source_label = Gtk.Label(label=_("Source (English)"), xalign=0)
        source_label.add_css_class("heading")
        editor_box.append(source_label)

        source_scroll = Gtk.ScrolledWindow()
        source_scroll.set_vexpand(True)
        source_scroll.set_min_content_height(80)

        self._source_view = Gtk.TextView()
        self._source_view.set_editable(False)
        self._source_view.set_cursor_visible(False)
        self._source_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._source_view.set_left_margin(8)
        self._source_view.set_right_margin(8)
        self._source_view.set_top_margin(4)
        self._source_view.set_bottom_margin(4)
        self._source_view.add_css_class("monospace")
        source_scroll.set_child(self._source_view)

        frame_src = Gtk.Frame()
        frame_src.set_child(source_scroll)
        editor_box.append(frame_src)

        # Translation (msgstr)
        trans_label = Gtk.Label(label=_("Translation"), xalign=0)
        trans_label.add_css_class("heading")
        editor_box.append(trans_label)

        trans_scroll = Gtk.ScrolledWindow()
        trans_scroll.set_vexpand(True)
        trans_scroll.set_min_content_height(80)

        self._trans_view = Gtk.TextView()
        self._trans_view.set_editable(True)
        self._trans_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._trans_view.set_left_margin(8)
        self._trans_view.set_right_margin(8)
        self._trans_view.set_top_margin(4)
        self._trans_view.set_bottom_margin(4)
        self._trans_view.add_css_class("monospace")
        trans_scroll.set_child(self._trans_view)

        frame_tr = Gtk.Frame()
        frame_tr.set_child(trans_scroll)
        editor_box.append(frame_tr)

        # Action buttons row
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._fuzzy_toggle = Gtk.ToggleButton(label=_("Fuzzy"))
        self._fuzzy_toggle.set_tooltip_text(_("Toggle fuzzy flag"))
        actions.append(self._fuzzy_toggle)

        copy_btn = Gtk.Button(label=_("Copy Source"))
        copy_btn.set_tooltip_text(_("Copy source to translation"))
        copy_btn.connect("clicked", self._on_copy_source)
        actions.append(copy_btn)

        # Navigation
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        actions.append(spacer)

        prev_btn = Gtk.Button(icon_name="go-previous-symbolic")
        prev_btn.set_tooltip_text(_("Previous entry"))
        prev_btn.connect("clicked", self._on_prev)
        actions.append(prev_btn)

        next_btn = Gtk.Button(icon_name="go-next-symbolic")
        next_btn.set_tooltip_text(_("Next entry"))
        next_btn.connect("clicked", self._on_next)
        actions.append(next_btn)

        editor_box.append(actions)

        paned.set_end_child(editor_box)

        main_box.append(paned)
        toolbar_view.set_content(main_box)
        self.set_child(toolbar_view)

    def _load_file(self) -> None:
        if polib is None:
            self._window.show_toast(
                _("polib is not installed. Install it with: pip install polib")
            )
            return

        try:
            self._po_file = polib.pofile(self._po_path)
        except Exception as exc:
            self._window.show_toast(_("Failed to load PO file: %s") % str(exc))
            return

        # Get translatable entries (skip header)
        self._entries = [e for e in self._po_file if e.msgid]
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self._search_text.lower()
        mode_idx = self._filter_dropdown.get_selected()
        modes = ["all", "untranslated", "fuzzy", "translated"]
        mode = modes[mode_idx] if mode_idx < len(modes) else "all"

        self._filtered = []
        for entry in self._entries:
            # Search filter
            if query:
                if query not in entry.msgid.lower() and query not in entry.msgstr.lower():
                    continue

            # Status filter
            if mode == "untranslated" and entry.msgstr:
                continue
            elif mode == "fuzzy" and "fuzzy" not in entry.flags:
                continue
            elif mode == "translated" and (not entry.msgstr or "fuzzy" in entry.flags):
                continue

            self._filtered.append(entry)

        self._rebuild_list()
        self._update_status()

    def _rebuild_list(self) -> None:
        # Save current before rebuilding
        self._save_current_entry()

        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        for i, entry in enumerate(self._filtered):
            row = self._make_entry_row(entry, i)
            self._list_box.append(row)

        self._current_idx = -1

    def _make_entry_row(self, entry, idx: int) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._entry_idx = idx

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        # msgid preview
        preview = entry.msgid[:60]
        if len(entry.msgid) > 60:
            preview += "…"
        lbl = Gtk.Label(label=preview, xalign=0)
        lbl.set_ellipsize(3)  # Pango.EllipsizeMode.END
        box.append(lbl)

        # Status indicator
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        if "fuzzy" in entry.flags:
            badge = Gtk.Label(label="⚠ " + _("Fuzzy"))
            badge.add_css_class("warning")
            badge.add_css_class("caption")
            status_box.append(badge)
        elif not entry.msgstr:
            badge = Gtk.Label(label="✗ " + _("Untranslated"))
            badge.add_css_class("error")
            badge.add_css_class("caption")
            status_box.append(badge)
        else:
            badge = Gtk.Label(label="✓ " + _("Translated"))
            badge.add_css_class("success")
            badge.add_css_class("caption")
            status_box.append(badge)
        box.append(status_box)

        row.set_child(box)
        return row

    def _update_status(self) -> None:
        if not self._entries:
            self._status_label.set_label(_("No entries"))
            return

        total = len(self._entries)
        translated = sum(
            1 for e in self._entries if e.msgstr and "fuzzy" not in e.flags
        )
        fuzzy = sum(1 for e in self._entries if "fuzzy" in e.flags)
        untranslated = total - translated - fuzzy

        self._status_label.set_label(
            _("%(translated)d/%(total)d translated, %(fuzzy)d fuzzy, %(shown)d shown")
            % {
                "translated": translated,
                "total": total,
                "fuzzy": fuzzy,
                "shown": len(self._filtered),
            }
        )

    def _on_entry_selected(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        # Save previous
        self._save_current_entry()

        if row is None:
            self._current_idx = -1
            return

        idx = row._entry_idx
        if idx < 0 or idx >= len(self._filtered):
            return

        self._current_idx = idx
        entry = self._filtered[idx]

        self._source_view.get_buffer().set_text(entry.msgid)
        self._trans_view.get_buffer().set_text(entry.msgstr)
        self._fuzzy_toggle.set_active("fuzzy" in entry.flags)

    def _save_current_entry(self) -> None:
        if self._current_idx < 0 or self._current_idx >= len(self._filtered):
            return

        entry = self._filtered[self._current_idx]
        buf = self._trans_view.get_buffer()
        start, end = buf.get_bounds()
        entry.msgstr = buf.get_text(start, end, True)

        if self._fuzzy_toggle.get_active():
            if "fuzzy" not in entry.flags:
                entry.flags.append("fuzzy")
        else:
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")

    def _on_copy_source(self, btn: Gtk.Button) -> None:
        if self._current_idx < 0 or self._current_idx >= len(self._filtered):
            return
        entry = self._filtered[self._current_idx]
        self._trans_view.get_buffer().set_text(entry.msgid)

    def _on_prev(self, btn: Gtk.Button) -> None:
        if self._current_idx > 0:
            row = self._list_box.get_row_at_index(self._current_idx - 1)
            if row:
                self._list_box.select_row(row)

    def _on_next(self, btn: Gtk.Button) -> None:
        if self._current_idx < len(self._filtered) - 1:
            row = self._list_box.get_row_at_index(self._current_idx + 1)
            if row:
                self._list_box.select_row(row)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._search_text = entry.get_text()
        self._apply_filter()

    def _on_filter_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        self._apply_filter()

    def _on_save(self, btn: Gtk.Button) -> None:
        self._save_current_entry()
        if self._po_file:
            try:
                self._po_file.save(self._po_path)
                self._window.show_toast(_("Saved to %s") % Path(self._po_path).name)
                self._update_status()
            except Exception as exc:
                self._window.show_toast(_("Save failed: %s") % str(exc))

    def _on_submit(self, btn: Gtk.Button) -> None:
        self._save_current_entry()
        if self._po_file:
            try:
                self._po_file.save(self._po_path)
            except Exception:
                pass
        self._window.show_submit_dialog(self._po_path, self._pkg)
