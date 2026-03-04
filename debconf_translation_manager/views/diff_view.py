"""Diff View — side-by-side comparison of old vs new template strings
when templates change, with color-coded diff highlighting."""

from __future__ import annotations

import gettext
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from debconf_translation_manager.services.notifier import ChangeNotifier, get_mock_changes
from debconf_translation_manager.services.template_parser import get_mock_diff_data
from debconf_translation_manager.widgets.diff_widget import DiffWidget
from debconf_translation_manager.widgets.filter_bar import FilterBar
from debconf_translation_manager.widgets.status_badge import StatusBadge

_ = gettext.gettext


class DiffView(Gtk.Box):
    """Side-by-side diff view for template changes.

    Shows changed packages in a list on the left and a color-coded
    character-level diff on the right.
    """

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._changes = get_mock_diff_data()
        self._filtered = list(self._changes)
        self._notifier = ChangeNotifier()
        self._build_ui()
        self._populate()

    def focus_search(self) -> None:
        self._filter_bar.focus_search()

    def get_export_data(self) -> list[dict[str, Any]]:
        return self._filtered

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        # Title row
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_row.set_margin_start(16)
        title_row.set_margin_end(16)
        title_row.set_margin_top(12)
        title_row.set_margin_bottom(4)

        title = Gtk.Label(label=_("Template Diff View"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        title_row.append(title)

        self._count_label = Gtk.Label()
        self._count_label.add_css_class("dim-label")
        title_row.append(self._count_label)

        check_btn = Gtk.Button(label=_("Check for Changes"))
        check_btn.set_tooltip_text(_("Poll for new template changes"))
        check_btn.connect("clicked", self._on_check_changes)
        title_row.append(check_btn)

        self.append(title_row)

        # Filter bar
        self._filter_bar = FilterBar(
            search_placeholder=_("Filter changes…"),
            filters=[
                (_("Type"), ["All", "modified", "added", "removed"]),
            ],
            on_changed=self._apply_filters,
        )
        self.append(self._filter_bar)

        # Summary strip
        summary = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        summary.set_margin_start(16)
        summary.set_margin_end(16)
        summary.set_margin_top(4)
        summary.set_margin_bottom(4)

        self._sum_modified = Gtk.Label()
        self._sum_modified.add_css_class("caption")
        summary.append(self._sum_modified)

        self._sum_added = Gtk.Label()
        self._sum_added.add_css_class("caption")
        self._sum_added.add_css_class("success")
        summary.append(self._sum_added)

        self._sum_removed = Gtk.Label()
        self._sum_removed.add_css_class("caption")
        self._sum_removed.add_css_class("error")
        summary.append(self._sum_removed)

        self.append(summary)
        self.append(Gtk.Separator())

        # Split: change list left, diff widget right
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(400)

        # Left: change list
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_size_request(280, -1)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(8)
        self._list_box.set_margin_end(4)
        self._list_box.set_margin_top(8)
        self._list_box.set_margin_bottom(8)
        self._list_box.connect("row-selected", self._on_change_selected)

        list_scroll.set_child(self._list_box)
        paned.set_start_child(list_scroll)

        # Right: diff display
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_box.set_margin_start(8)
        right_box.set_margin_end(16)
        right_box.set_margin_top(8)
        right_box.set_margin_bottom(8)

        # Change info header
        self._change_title = Gtk.Label(xalign=0)
        self._change_title.add_css_class("title-4")
        right_box.append(self._change_title)

        self._change_info = Gtk.Label(xalign=0)
        self._change_info.add_css_class("caption")
        self._change_info.add_css_class("dim-label")
        right_box.append(self._change_info)

        # The diff widget
        self._diff_widget = DiffWidget()
        self._diff_widget.set_vexpand(True)
        right_box.append(self._diff_widget)

        # Placeholder when nothing selected
        self._placeholder = Adw.StatusPage()
        self._placeholder.set_icon_name("view-dual-symbolic")
        self._placeholder.set_title(_("Select a change"))
        self._placeholder.set_description(
            _("Choose a changed template from the list to see a side-by-side diff.")
        )
        self._placeholder.set_vexpand(True)

        # Stack to switch between placeholder and diff
        self._detail_stack = Gtk.Stack()
        self._detail_stack.add_named(self._placeholder, "placeholder")
        self._detail_stack.add_named(right_box, "diff")
        self._detail_stack.set_visible_child_name("placeholder")

        paned.set_end_child(self._detail_stack)
        self.append(paned)

    # -- data -----------------------------------------------------------

    def _populate(self) -> None:
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = self._filter_bar.search_text
        type_filter = self._filter_bar.get_filter_value(_("Type"))

        self._filtered = []
        for c in self._changes:
            if query and query not in c["package"].lower() and query not in c["template"].lower():
                continue
            if type_filter and type_filter != "All" and c["change_type"] != type_filter:
                continue
            self._filtered.append(c)

        # Update summary
        modified = sum(1 for c in self._changes if c["change_type"] == "modified")
        added = sum(1 for c in self._changes if c["change_type"] == "added")
        removed = sum(1 for c in self._changes if c["change_type"] == "removed")
        self._sum_modified.set_label(_("Modified: %d") % modified)
        self._sum_added.set_label(_("Added: %d") % added)
        self._sum_removed.set_label(_("Removed: %d") % removed)
        self._count_label.set_label(f"({len(self._filtered)} {_('changes')})")

        self._rebuild_list()

    def _rebuild_list(self) -> None:
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        for change in self._filtered:
            row = self._make_change_row(change)
            self._list_box.append(row)

        self._detail_stack.set_visible_child_name("placeholder")

    def _make_change_row(self, change: dict[str, str]) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._change = change

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        # Package + template
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        pkg_label = Gtk.Label(label=change["package"], xalign=0)
        pkg_label.add_css_class("heading")
        pkg_label.set_hexpand(True)
        top.append(pkg_label)

        badge = StatusBadge(status=change["change_type"])
        top.append(badge)
        box.append(top)

        # Template + field
        detail = Gtk.Label(
            label=f"{change['template']} — {change['field']}",
            xalign=0,
        )
        detail.add_css_class("caption")
        detail.add_css_class("dim-label")
        detail.set_ellipsize(3)
        box.append(detail)

        row.set_child(box)
        return row

    # -- callbacks ------------------------------------------------------

    def _on_change_selected(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            self._detail_stack.set_visible_child_name("placeholder")
            return

        change = row._change
        self._change_title.set_label(f"{change['package']}: {change['field']}")
        self._change_info.set_label(
            f"{_('Template')}: {change['template']}  |  "
            f"{_('Change')}: {change['change_type']}"
        )
        self._diff_widget.set_diff(change["old"], change["new"])
        self._detail_stack.set_visible_child_name("diff")

    def _on_check_changes(self, btn: Gtk.Button) -> None:
        new_changes = self._notifier.load_mock_changes()
        if new_changes:
            # Merge into our list, avoiding duplicates
            existing = {(c["package"], c["template"], c["field"]) for c in self._changes}
            for nc in new_changes:
                key = (nc.package, nc.template_name, nc.field)
                if key not in existing:
                    self._changes.append({
                        "package": nc.package,
                        "template": nc.template_name,
                        "field": nc.field,
                        "old": nc.old_value,
                        "new": nc.new_value,
                        "change_type": nc.change_type,
                    })
            self._apply_filters()
            if self._window:
                self._window.show_notification(
                    _("%d template change(s) detected") % len(new_changes)
                )
                self._window.show_toast(_("Checked for changes"))
        else:
            if self._window:
                self._window.show_toast(_("No new changes found"))
