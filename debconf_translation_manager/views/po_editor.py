"""PO Editor view — edit po-debconf translation files side by side."""

from __future__ import annotations

import gettext
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from debconf_translation_manager.services.template_parser import get_mock_po_entries
from debconf_translation_manager.widgets.filter_bar import FilterBar
from debconf_translation_manager.widgets.status_badge import StatusBadge

_ = gettext.gettext


class POEditorView(Gtk.Box):
    """Side-by-side PO file editor with fuzzy marking and comments."""

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._entries = get_mock_po_entries("sv")
        self._filtered = list(self._entries)
        self._current_entry: dict[str, str] | None = None
        self._modified = False
        self._build_ui()
        self._populate()

    def focus_search(self) -> None:
        self._filter_bar.focus_search()

    def save(self) -> None:
        """Save current edits back to the entry list."""
        if self._current_entry is not None:
            self._save_current()
        self._modified = False
        if self._window:
            self._window.show_toast(_("PO entries saved"))

    def get_export_data(self) -> list[dict[str, Any]]:
        return self._filtered

    def _build_ui(self) -> None:
        # Title + stats
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.set_margin_start(16)
        title_box.set_margin_top(12)
        title_box.set_margin_bottom(4)
        title = Gtk.Label(label=_("PO Editor"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title_box.append(title)

        self._stats_label = Gtk.Label()
        self._stats_label.add_css_class("dim-label")
        title_box.append(self._stats_label)
        self.append(title_box)

        # Filter bar
        self._filter_bar = FilterBar(
            search_placeholder=_("Search strings…"),
            filters=[
                (_("Show"), ["All", "Untranslated", "Fuzzy", "Translated"]),
            ],
            on_changed=self._apply_filters,
        )
        self.append(self._filter_bar)
        self.append(Gtk.Separator())

        # Main split: entry list on left, editor on right
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(450)

        # Entry list
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_size_request(300, -1)

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

        # Editor panel
        editor = self._build_editor_panel()
        paned.set_end_child(editor)

        self.append(paned)

        # Validation bar
        self._validation_bar = Gtk.Revealer()
        self._validation_bar.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_UP
        )
        val_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        val_box.set_margin_start(16)
        val_box.set_margin_end(16)
        val_box.set_margin_top(4)
        val_box.set_margin_bottom(4)

        val_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        val_box.append(val_icon)
        self._val_label = Gtk.Label(xalign=0)
        self._val_label.add_css_class("warning")
        val_box.append(self._val_label)
        self._validation_bar.set_child(val_box)
        self.append(self._validation_bar)

    def _build_editor_panel(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(16)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        # Reference / comment info
        self._ref_label = Gtk.Label(xalign=0)
        self._ref_label.add_css_class("caption")
        self._ref_label.add_css_class("dim-label")
        box.append(self._ref_label)

        self._comment_label = Gtk.Label(xalign=0, wrap=True)
        self._comment_label.add_css_class("caption")
        box.append(self._comment_label)

        # Source (msgid)
        source_label = Gtk.Label(label=_("Source (English)"), xalign=0)
        source_label.add_css_class("heading")
        box.append(source_label)

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
        box.append(frame_src)

        # Translation (msgstr)
        trans_label = Gtk.Label(label=_("Translation"), xalign=0)
        trans_label.add_css_class("heading")
        box.append(trans_label)

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
        self._trans_view.get_buffer().connect("changed", self._on_translation_changed)
        trans_scroll.set_child(self._trans_view)

        frame_tr = Gtk.Frame()
        frame_tr.set_child(trans_scroll)
        box.append(frame_tr)

        # Actions row
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._fuzzy_check = Gtk.CheckButton(label=_("Fuzzy"))
        self._fuzzy_check.connect("toggled", self._on_fuzzy_toggled)
        actions.append(self._fuzzy_check)

        copy_btn = Gtk.Button(label=_("Copy Source"))
        copy_btn.connect("clicked", self._on_copy_source)
        actions.append(copy_btn)

        clear_btn = Gtk.Button(label=_("Clear Translation"))
        clear_btn.connect("clicked", self._on_clear_translation)
        actions.append(clear_btn)

        validate_btn = Gtk.Button(label=_("Validate"))
        validate_btn.add_css_class("suggested-action")
        validate_btn.connect("clicked", self._on_validate)
        actions.append(validate_btn)

        box.append(actions)

        # Translator comment
        comment_entry_label = Gtk.Label(label=_("Translator Comment"), xalign=0)
        comment_entry_label.add_css_class("caption")
        box.append(comment_entry_label)

        self._comment_entry = Gtk.Entry()
        self._comment_entry.set_placeholder_text(_("Add a comment…"))
        box.append(self._comment_entry)

        return box

    def _populate(self) -> None:
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = self._filter_bar.search_text
        show = self._filter_bar.get_filter_value(_("Show"))

        self._filtered = []
        for e in self._entries:
            if query and query not in e["msgid"].lower() and query not in e["msgstr"].lower():
                continue
            if show == "Untranslated" and e["msgstr"]:
                continue
            if show == "Fuzzy" and e["flags"] != "fuzzy":
                continue
            if show == "Translated" and not e["msgstr"]:
                continue
            self._filtered.append(e)

        self._rebuild_list()

    def _rebuild_list(self) -> None:
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        total = len(self._entries)
        translated = sum(1 for e in self._entries if e["msgstr"] and e["flags"] != "fuzzy")
        fuzzy = sum(1 for e in self._entries if e["flags"] == "fuzzy")
        untranslated = total - translated - fuzzy
        self._stats_label.set_label(
            f"T:{translated}  F:{fuzzy}  U:{untranslated}  ({len(self._filtered)} shown)"
        )

        for entry in self._filtered:
            row = self._make_entry_row(entry)
            self._list_box.append(row)

    def _make_entry_row(self, entry: dict[str, str]) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._entry = entry

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        # msgid preview
        msgid_preview = entry["msgid"][:80]
        if len(entry["msgid"]) > 80:
            msgid_preview += "…"
        lbl = Gtk.Label(label=msgid_preview, xalign=0)
        lbl.set_ellipsize(3)
        box.append(lbl)

        # Status indicator
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if entry["flags"] == "fuzzy":
            badge = StatusBadge(status="fuzzy")
            info_box.append(badge)
        elif entry["msgstr"]:
            badge = StatusBadge(status="translated")
            info_box.append(badge)
        else:
            badge = StatusBadge(status="untranslated")
            info_box.append(badge)

        ref = Gtk.Label(label=entry.get("reference", ""))
        ref.add_css_class("caption")
        ref.add_css_class("dim-label")
        info_box.append(ref)

        box.append(info_box)
        row.set_child(box)
        return row

    def _on_entry_selected(
        self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None
    ) -> None:
        # Save previous entry
        if self._current_entry is not None:
            self._save_current()

        if row is None:
            self._current_entry = None
            return

        entry = row._entry
        self._current_entry = entry

        self._ref_label.set_label(entry.get("reference", ""))
        self._comment_label.set_label(entry.get("comment", ""))
        self._source_view.get_buffer().set_text(entry["msgid"])
        self._trans_view.get_buffer().set_text(entry["msgstr"])
        self._fuzzy_check.set_active(entry["flags"] == "fuzzy")
        self._comment_entry.set_text("")
        self._validation_bar.set_reveal_child(False)

    def _save_current(self) -> None:
        if self._current_entry is None:
            return
        buf = self._trans_view.get_buffer()
        start, end = buf.get_bounds()
        self._current_entry["msgstr"] = buf.get_text(start, end, True)
        self._current_entry["flags"] = "fuzzy" if self._fuzzy_check.get_active() else ""

    def _on_translation_changed(self, buf: Gtk.TextBuffer) -> None:
        self._modified = True
        self._validation_bar.set_reveal_child(False)

    def _on_fuzzy_toggled(self, btn: Gtk.CheckButton) -> None:
        self._modified = True

    def _on_copy_source(self, btn: Gtk.Button) -> None:
        """Copy source text into translation field."""
        if self._current_entry:
            self._trans_view.get_buffer().set_text(self._current_entry["msgid"])

    def _on_clear_translation(self, btn: Gtk.Button) -> None:
        self._trans_view.get_buffer().set_text("")

    def _on_validate(self, btn: Gtk.Button) -> None:
        """Run validation checks on the current entry."""
        if self._current_entry is None:
            return

        issues: list[str] = []
        buf = self._trans_view.get_buffer()
        start, end = buf.get_bounds()
        translation = buf.get_text(start, end, True)
        source = self._current_entry["msgid"]

        if not translation:
            issues.append(_("Translation is empty"))

        # Check format strings match
        import re

        src_formats = set(re.findall(r"%[sdf]|%\(\w+\)[sdf]", source))
        tr_formats = set(re.findall(r"%[sdf]|%\(\w+\)[sdf]", translation))
        if src_formats != tr_formats:
            issues.append(
                _("Format string mismatch: source has %s, translation has %s")
                % (src_formats or "none", tr_formats or "none")
            )

        # Check trailing newline consistency
        if source.endswith("\n") and not translation.endswith("\n"):
            issues.append(_("Source ends with newline but translation does not"))

        # Length check (warn if translation is >2x longer)
        if translation and len(translation) > len(source) * 2:
            issues.append(
                _("Translation is significantly longer than source (%d vs %d chars)")
                % (len(translation), len(source))
            )

        # Encoding check
        try:
            translation.encode("utf-8")
        except UnicodeEncodeError:
            issues.append(_("Translation contains invalid UTF-8 characters"))

        if issues:
            self._val_label.set_label(" | ".join(issues))
            self._validation_bar.set_reveal_child(True)
        else:
            self._validation_bar.set_reveal_child(False)
            if self._window:
                self._window.show_toast(_("Validation passed"))
