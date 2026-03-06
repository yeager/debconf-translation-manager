"""PO Editor View — built-in translation editor with side-by-side layout."""

from __future__ import annotations

import gettext
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

if TYPE_CHECKING:
    from debconf_translation_manager.window import MainWindow

_ = gettext.gettext

try:
    import polib
except ImportError:
    polib = None


class PoEditorView(Gtk.Box):
    """Side-by-side PO file editor panel."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window
        self._po_file = None
        self._po_path: str | None = None
        self._pkg = None
        self._entries: list = []
        self._filtered: list = []
        self._current_idx: int = -1
        self._search_text = ""
        self._build_ui()

    def _build_ui(self) -> None:
        # Header
        header = Adw.HeaderBar()
        self._title_label = Gtk.Label(label=_("Editor"))
        header.set_title_widget(self._title_label)

        save_btn = Gtk.Button(icon_name="document-save-symbolic")
        save_btn.set_tooltip_text(_("Save (Ctrl+S)"))
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        open_ext_btn = Gtk.Button(icon_name="text-editor-symbolic")
        open_ext_btn.set_tooltip_text(_("Open in external editor"))
        open_ext_btn.connect("clicked", self._on_open_external)
        header.pack_end(open_ext_btn)

        self.append(header)

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

        self.append(filter_box)

        # Status bar
        self._status_label = Gtk.Label(xalign=0)
        self._status_label.add_css_class("dim-label")
        self._status_label.add_css_class("caption")
        self._status_label.set_margin_start(12)
        self._status_label.set_margin_bottom(4)
        self.append(self._status_label)

        self.append(Gtk.Separator())

        # Main content: paned (list | editor)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(350)

        # Left: entry list
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_size_request(250, -1)

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

        # Right: editor area
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
        trans_label = Gtk.Label(label=_("Translation (Swedish)"), xalign=0)
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

        # Action buttons
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._fuzzy_toggle = Gtk.ToggleButton(label=_("Fuzzy"))
        self._fuzzy_toggle.set_tooltip_text(_("Toggle fuzzy flag"))
        actions.append(self._fuzzy_toggle)

        copy_btn = Gtk.Button(label=_("Copy Source"))
        copy_btn.set_tooltip_text(_("Copy source to translation"))
        copy_btn.connect("clicked", self._on_copy_source)
        actions.append(copy_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        actions.append(spacer)

        prev_untr_btn = Gtk.Button(label=_("⏮ Untranslated"))
        prev_untr_btn.set_tooltip_text(_("Jump to previous untranslated/fuzzy"))
        prev_untr_btn.connect("clicked", self._on_prev_untranslated)
        actions.append(prev_untr_btn)

        prev_btn = Gtk.Button(icon_name="go-previous-symbolic")
        prev_btn.set_tooltip_text(_("Previous entry"))
        prev_btn.connect("clicked", self._on_prev)
        actions.append(prev_btn)

        next_btn = Gtk.Button(icon_name="go-next-symbolic")
        next_btn.set_tooltip_text(_("Next entry"))
        next_btn.connect("clicked", self._on_next)
        actions.append(next_btn)

        next_untr_btn = Gtk.Button(label=_("Untranslated ⏭"))
        next_untr_btn.set_tooltip_text(_("Jump to next untranslated/fuzzy"))
        next_untr_btn.connect("clicked", self._on_next_untranslated)
        actions.append(next_untr_btn)

        editor_box.append(actions)

        paned.set_end_child(editor_box)
        self.append(paned)

        # Empty state
        self._empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._empty_status = Adw.StatusPage()
        self._empty_status.set_title(_("No File Loaded"))
        self._empty_status.set_description(
            _("Select a package and download its PO file to start translating.")
        )
        self._empty_status.set_icon_name("document-edit-symbolic")
        self._empty_box.append(self._empty_status)

        # Use a stack for empty/editor states
        self._editor_stack = Gtk.Stack()
        # We need to reparent: remove paned, add both to stack
        # Actually, let's just control visibility
        self._paned_widget = paned

        # Show empty state initially
        self._status_label.set_label(_("No file loaded"))

    def load_file(self, po_path: str, pkg=None) -> None:
        """Load a PO file into the editor."""
        if polib is None:
            self._window.show_toast(
                _("polib is not installed. Install it with: pip install polib")
            )
            return

        self._po_path = po_path
        self._pkg = pkg

        try:
            self._po_file = polib.pofile(po_path)
        except Exception as exc:
            self._window.show_toast(_("Failed to load PO file: %s") % str(exc))
            return

        name = pkg.package if pkg else Path(po_path).stem
        self._title_label.set_label(_("Editor: %s") % name)
        self._entries = [e for e in self._po_file if e.msgid]
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self._search_text.lower()
        mode_idx = self._filter_dropdown.get_selected()
        modes = ["all", "untranslated", "fuzzy", "translated"]
        mode = modes[mode_idx] if mode_idx < len(modes) else "all"

        self._filtered = []
        for entry in self._entries:
            if query:
                if query not in entry.msgid.lower() and query not in entry.msgstr.lower():
                    continue
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

        preview = entry.msgid[:60]
        if len(entry.msgid) > 60:
            preview += "…"
        lbl = Gtk.Label(label=preview, xalign=0)
        lbl.set_ellipsize(3)  # END
        box.append(lbl)

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
            self._status_label.set_label(_("No file loaded"))
            return

        total = len(self._entries)
        translated = sum(
            1 for e in self._entries if e.msgstr and "fuzzy" not in e.flags
        )
        fuzzy = sum(1 for e in self._entries if "fuzzy" in e.flags)

        self._status_label.set_label(
            _("%(translated)d/%(total)d translated, %(fuzzy)d fuzzy, %(shown)d shown")
            % {
                "translated": translated,
                "total": total,
                "fuzzy": fuzzy,
                "shown": len(self._filtered),
            }
        )

    def _on_entry_selected(self, listbox, row) -> None:
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

    def _on_copy_source(self, btn) -> None:
        if self._current_idx < 0 or self._current_idx >= len(self._filtered):
            return
        entry = self._filtered[self._current_idx]
        self._trans_view.get_buffer().set_text(entry.msgid)

    def _on_prev(self, btn) -> None:
        if self._current_idx > 0:
            row = self._list_box.get_row_at_index(self._current_idx - 1)
            if row:
                self._list_box.select_row(row)

    def _on_next(self, btn) -> None:
        if self._current_idx < len(self._filtered) - 1:
            row = self._list_box.get_row_at_index(self._current_idx + 1)
            if row:
                self._list_box.select_row(row)

    def _on_prev_untranslated(self, btn) -> None:
        """Jump to previous untranslated or fuzzy entry."""
        for i in range(self._current_idx - 1, -1, -1):
            entry = self._filtered[i]
            if not entry.msgstr or "fuzzy" in entry.flags:
                row = self._list_box.get_row_at_index(i)
                if row:
                    self._list_box.select_row(row)
                return

    def _on_next_untranslated(self, btn) -> None:
        """Jump to next untranslated or fuzzy entry."""
        for i in range(self._current_idx + 1, len(self._filtered)):
            entry = self._filtered[i]
            if not entry.msgstr or "fuzzy" in entry.flags:
                row = self._list_box.get_row_at_index(i)
                if row:
                    self._list_box.select_row(row)
                return

    def _on_save(self, btn) -> None:
        self._save_current_entry()
        if self._po_file and self._po_path:
            try:
                self._po_file.save(self._po_path)
                self._window.show_toast(_("Saved to %s") % Path(self._po_path).name)
                self._update_status()
            except Exception as exc:
                self._window.show_toast(_("Save failed: %s") % str(exc))

    def _on_open_external(self, btn) -> None:
        """Open the LOCAL .po file in the system's default editor."""
        if not self._po_path:
            self._window.show_toast(_("No file loaded"))
            return

        path = self._po_path
        if not os.path.isfile(path):
            self._window.show_toast(_("File not found: %s") % path)
            return

        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
            self._window.show_toast(_("Opened %s in external editor") % Path(path).name)
        except Exception as exc:
            self._window.show_toast(_("Could not open file: %s") % str(exc))

    def _on_search_changed(self, entry) -> None:
        self._search_text = entry.get_text()
        self._apply_filter()

    def _on_filter_changed(self, dropdown, _pspec) -> None:
        self._apply_filter()
