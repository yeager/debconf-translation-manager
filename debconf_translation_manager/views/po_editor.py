"""PO Editor view — edit po-debconf translation files side by side."""

from __future__ import annotations

import gettext
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from debconf_translation_manager.services.settings import Settings
from debconf_translation_manager.services.template_parser import (
    POEntry,
    get_mock_po_entries,
    parse_po_file,
    po_entry_to_string,
)
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
        self._current_file_path: str | None = None
        self._current_package: str | None = None
        self._po_entries: list[POEntry] | None = None
        self._build_ui()
        self._populate()

    def focus_search(self) -> None:
        self._filter_bar.focus_search()

    def load_po_file(self, path: str, package: str | None = None) -> None:
        """Load a .po file from disk into the editor."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as exc:
            if self._window:
                self._window.show_toast(_("Failed to open file: %s") % str(exc))
            return

        self._po_entries = parse_po_file(content)
        self._current_file_path = path
        self._current_package = package or Path(path).stem
        self._current_entry = None

        # Convert POEntry objects to the dict format used by the editor
        self._entries = []
        for entry in self._po_entries:
            if not entry.msgid:  # skip header entry
                continue
            self._entries.append({
                "msgid": entry.msgid,
                "msgstr": entry.msgstr,
                "flags": "fuzzy" if entry.is_fuzzy else "",
                "comment": entry.comment,
                "reference": ", ".join(entry.references),
                "translator_comment": entry.translator_comment,
            })

        self._filtered = list(self._entries)
        self._modified = False
        self._update_file_label()
        self._rebuild_list()

        if self._window:
            self._window.show_toast(
                _("Loaded %d entries from %s") % (len(self._entries), Path(path).name)
            )

    def set_package(self, package: str) -> None:
        """Set the current package name (used when navigating from browser)."""
        self._current_package = package

    def save(self) -> None:
        """Save current edits back to the entry list."""
        if self._current_entry is not None:
            self._save_current()
        self._modified = False
        if self._window:
            self._window.show_toast(_("PO entries saved"))

    def save_to_file(self, path: str | None = None) -> str | None:
        """Save the current PO entries to a file. Returns the path or None."""
        if self._current_entry is not None:
            self._save_current()

        target = path or self._current_file_path
        if not target:
            return None

        # Rebuild PO content
        content = self._build_po_content()
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            self._modified = False
            self._current_file_path = target
            return target
        except OSError as exc:
            if self._window:
                self._window.show_toast(_("Failed to save: %s") % str(exc))
            return None

    def get_file_path(self) -> str | None:
        return self._current_file_path

    def get_package_name(self) -> str | None:
        return self._current_package

    def get_export_data(self) -> list[dict[str, Any]]:
        return self._filtered

    def _build_po_content(self) -> str:
        """Build PO file content from current entries."""
        lines: list[str] = []

        # Write header if we have original POEntry data
        if self._po_entries:
            for entry in self._po_entries:
                if not entry.msgid:  # header
                    lines.append(po_entry_to_string(entry))
                    lines.append("")
                    break

        # Write regular entries
        for e in self._entries:
            if e.get("translator_comment"):
                for cl in e["translator_comment"].splitlines():
                    lines.append(f"# {cl}")
            if e.get("comment"):
                for cl in e["comment"].splitlines():
                    lines.append(f"#. {cl}")
            if e.get("reference"):
                lines.append(f"#: {e['reference']}")
            if e.get("flags") == "fuzzy":
                lines.append("#, fuzzy")

            msgid = e["msgid"]
            msgstr = e["msgstr"]

            # Handle multi-line strings
            if "\n" in msgid:
                lines.append('msgid ""')
                for part in msgid.split("\n"):
                    escaped = part.replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(f'"{escaped}\\n"')
            else:
                escaped = msgid.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'msgid "{escaped}"')

            if "\n" in msgstr:
                lines.append('msgstr ""')
                for part in msgstr.split("\n"):
                    escaped = part.replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(f'"{escaped}\\n"')
            else:
                escaped = msgstr.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'msgstr "{escaped}"')

            lines.append("")

        return "\n".join(lines)

    def _build_ui(self) -> None:
        # Title + stats + file buttons
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.set_margin_start(16)
        title_box.set_margin_end(16)
        title_box.set_margin_top(12)
        title_box.set_margin_bottom(4)
        title = Gtk.Label(label=_("PO Editor"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title_box.append(title)

        self._stats_label = Gtk.Label()
        self._stats_label.add_css_class("dim-label")
        self._stats_label.set_hexpand(True)
        title_box.append(self._stats_label)

        # Open file button
        open_btn = Gtk.Button(icon_name="document-open-symbolic")
        open_btn.set_tooltip_text(_("Open PO file"))
        open_btn.connect("clicked", self._on_open_file)
        title_box.append(open_btn)

        # Save file button
        save_btn = Gtk.Button(icon_name="document-save-symbolic")
        save_btn.set_tooltip_text(_("Save PO file"))
        save_btn.connect("clicked", self._on_save_file)
        title_box.append(save_btn)

        # Save As button
        saveas_btn = Gtk.Button(icon_name="document-save-as-symbolic")
        saveas_btn.set_tooltip_text(_("Save PO file as…"))
        saveas_btn.connect("clicked", self._on_save_as)
        title_box.append(saveas_btn)

        header_btn = Gtk.Button(label=_("Edit Header"))
        header_btn.set_icon_name("document-properties-symbolic")
        header_btn.connect("clicked", self._on_edit_header)
        title_box.append(header_btn)

        self.append(title_box)

        # File info label
        self._file_label = Gtk.Label(xalign=0)
        self._file_label.add_css_class("dim-label")
        self._file_label.add_css_class("caption")
        self._file_label.set_margin_start(16)
        self._file_label.set_margin_bottom(4)
        self.append(self._file_label)
        self._update_file_label()

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

        # Bottom action bar
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom_bar.set_margin_start(16)
        bottom_bar.set_margin_end(16)
        bottom_bar.set_margin_top(4)
        bottom_bar.set_margin_bottom(8)

        submit_btn = Gtk.Button(label=_("Submit via BTS"))
        submit_btn.set_icon_name("mail-send-symbolic")
        submit_btn.connect("clicked", self._on_submit_bts)
        bottom_bar.append(submit_btn)

        self.append(bottom_bar)

    def _update_file_label(self) -> None:
        if self._current_file_path:
            fname = Path(self._current_file_path).name
            pkg = self._current_package or ""
            self._file_label.set_label(
                f"{_('File')}: {fname}" + (f"  ({pkg})" if pkg else "")
            )
        else:
            self._file_label.set_label(_("No file loaded — using mock data"))

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
        self._comment_entry.set_text(entry.get("translator_comment", ""))
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
        if self._current_entry:
            self._trans_view.get_buffer().set_text(self._current_entry["msgid"])

    def _on_clear_translation(self, btn: Gtk.Button) -> None:
        self._trans_view.get_buffer().set_text("")

    def _on_validate(self, btn: Gtk.Button) -> None:
        if self._current_entry is None:
            return

        issues: list[str] = []
        buf = self._trans_view.get_buffer()
        start, end = buf.get_bounds()
        translation = buf.get_text(start, end, True)
        source = self._current_entry["msgid"]

        if not translation:
            issues.append(_("Translation is empty"))

        src_formats = set(re.findall(r"%[sdf]|%\(\w+\)[sdf]", source))
        tr_formats = set(re.findall(r"%[sdf]|%\(\w+\)[sdf]", translation))
        if src_formats != tr_formats:
            issues.append(
                _("Format string mismatch: source has %s, translation has %s")
                % (src_formats or "none", tr_formats or "none")
            )

        if source.endswith("\n") and not translation.endswith("\n"):
            issues.append(_("Source ends with newline but translation does not"))

        if translation and len(translation) > len(source) * 2:
            issues.append(
                _("Translation is significantly longer than source (%d vs %d chars)")
                % (len(translation), len(source))
            )

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

    # ── File I/O ───────────────────────────────────────────────────────

    def _on_open_file(self, btn: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        ff = Gtk.FileFilter()
        ff.set_name(_("PO files"))
        ff.add_pattern("*.po")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(ff)
        dialog.set_filters(filters)
        dialog.open(self._window, None, self._on_file_opened)

    def _on_file_opened(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = dialog.open_finish(result)
            path = gfile.get_path()
            if path:
                self.load_po_file(path)
        except GLib.Error:
            pass

    def _on_save_file(self, btn: Gtk.Button) -> None:
        if self._current_file_path:
            path = self.save_to_file()
            if path and self._window:
                self._window.show_toast(_("Saved to %s") % Path(path).name)
        else:
            self._on_save_as(btn)

    def _on_save_as(self, btn: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        pkg = self._current_package or "translation"
        lang = Settings.get().language_code
        dialog.set_initial_name(f"{pkg}_{lang}.po")
        dialog.save(self._window, None, self._on_save_as_ready)

    def _on_save_as_ready(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = dialog.save_finish(result)
            path = gfile.get_path()
            if path:
                saved = self.save_to_file(path)
                if saved and self._window:
                    self._update_file_label()
                    self._window.show_toast(_("Saved to %s") % Path(saved).name)
        except GLib.Error:
            pass

    def _on_submit_bts(self, btn: Gtk.Button) -> None:
        """Save and navigate to BTS workflow."""
        if self._current_entry is not None:
            self._save_current()

        if self._window:
            self._window.navigate_to_bts(
                package=self._current_package,
                po_file_path=self._current_file_path,
            )

    # -- PO Header editor -----------------------------------------------

    _po_header: dict[str, str] = {
        "translator_name": "",
        "translator_email": "",
        "year": "",
        "team": "Swedish <debian-l10n-swedish@lists.debian.org>",
        "language": "sv",
        "header_comment": "",
    }

    def _on_edit_header(self, btn: Gtk.Button) -> None:
        settings = Settings.get()
        year = str(datetime.now().year)

        dialog = Adw.Dialog()
        dialog.set_title(_("Edit PO Header"))
        dialog.set_content_width(500)
        dialog.set_content_height(520)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()

        apply_btn = Gtk.Button(label=_("Apply"))
        apply_btn.add_css_class("suggested-action")
        header.pack_end(apply_btn)
        toolbar.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()

        clamp = Adw.Clamp()
        clamp.set_maximum_size(460)
        clamp.set_margin_top(12)
        clamp.set_margin_bottom(12)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        translator_group = Adw.PreferencesGroup()
        translator_group.set_title(_("Translator"))

        name_row = Adw.EntryRow()
        name_row.set_title(_("Name"))
        name_row.set_text(
            self._po_header.get("translator_name") or settings.translator_name
        )
        translator_group.add(name_row)

        email_row = Adw.EntryRow()
        email_row.set_title(_("Email"))
        email_row.set_text(
            self._po_header.get("translator_email") or settings.translator_email
        )
        translator_group.add(email_row)

        year_row = Adw.EntryRow()
        year_row.set_title(_("Year"))
        year_row.set_text(self._po_header.get("year") or year)
        translator_group.add(year_row)

        last_translator_row = Adw.EntryRow()
        last_translator_row.set_title(_("Last-Translator"))
        last_translator_row.set_editable(False)
        translator_group.add(last_translator_row)

        def _update_last_translator(*_args: Any) -> None:
            n = name_row.get_text().strip()
            e = email_row.get_text().strip()
            if n and e:
                last_translator_row.set_text(f"{n} <{e}>")
            elif n:
                last_translator_row.set_text(n)
            else:
                last_translator_row.set_text("")

        name_row.connect("changed", _update_last_translator)
        email_row.connect("changed", _update_last_translator)
        _update_last_translator()

        content.append(translator_group)

        lang_group = Adw.PreferencesGroup()
        lang_group.set_title(_("Language"))

        team_row = Adw.EntryRow()
        team_row.set_title(_("Language-Team"))
        team_row.set_text(self._po_header.get("team", ""))
        lang_group.add(team_row)

        lang_row = Adw.EntryRow()
        lang_row.set_title(_("Language"))
        lang_row.set_text(
            self._po_header.get("language") or settings.language_code
        )
        lang_group.add(lang_row)

        content.append(lang_group)

        comment_group = Adw.PreferencesGroup()
        comment_group.set_title(_("Header Comment"))
        comment_group.set_description(
            _("Translator credit line added to the PO header comment")
        )

        comment_label = Gtk.Label(xalign=0, wrap=True, selectable=True)
        comment_label.add_css_class("monospace")
        comment_label.add_css_class("caption")
        comment_label.set_margin_start(12)
        comment_label.set_margin_end(12)
        comment_label.set_margin_top(8)
        comment_label.set_margin_bottom(8)

        def _update_comment_preview(*_args: Any) -> None:
            n = name_row.get_text().strip()
            e = email_row.get_text().strip()
            y = year_row.get_text().strip()
            if n and e and y:
                comment_label.set_label(f"# {n} <{e}>, {y}.")
            elif n and y:
                comment_label.set_label(f"# {n}, {y}.")
            else:
                comment_label.set_label("")

        name_row.connect("changed", _update_comment_preview)
        email_row.connect("changed", _update_comment_preview)
        year_row.connect("changed", _update_comment_preview)
        _update_comment_preview()

        comment_group.add(comment_label)
        content.append(comment_group)

        clamp.set_child(content)
        scroll.set_child(clamp)
        toolbar.set_content(scroll)
        dialog.set_child(toolbar)

        def _on_apply(_btn: Gtk.Button) -> None:
            name = name_row.get_text().strip()
            email = email_row.get_text().strip()
            yr = year_row.get_text().strip()
            team = team_row.get_text().strip()
            lang = lang_row.get_text().strip()

            self._po_header["translator_name"] = name
            self._po_header["translator_email"] = email
            self._po_header["year"] = yr
            self._po_header["team"] = team
            self._po_header["language"] = lang

            if name and email and yr:
                credit = f"# {name} <{email}>, {yr}."
            elif name and yr:
                credit = f"# {name}, {yr}."
            else:
                credit = ""

            self._po_header["header_comment"] = self._update_translator_credit(
                self._po_header.get("header_comment", ""), credit, name
            )

            dialog.close()
            if self._window:
                self._window.show_toast(_("PO header updated"))

        apply_btn.connect("clicked", _on_apply)
        dialog.present(self._window)

    @staticmethod
    def _update_translator_credit(
        existing_comment: str, new_credit: str, translator_name: str
    ) -> str:
        if not new_credit:
            return existing_comment

        lines = existing_comment.split("\n") if existing_comment else []
        updated = False

        if translator_name:
            pattern = re.compile(
                r"^#\s*" + re.escape(translator_name) + r"\s*<.*>,\s*\d{4}\.$"
            )
            for i, line in enumerate(lines):
                if pattern.match(line):
                    lines[i] = new_credit
                    updated = True
                    break

        if not updated:
            lines.append(new_credit)

        return "\n".join(lines)
