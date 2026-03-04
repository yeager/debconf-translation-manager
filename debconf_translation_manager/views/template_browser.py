"""Template Browser view — browse/search debconf templates."""

from __future__ import annotations

import gettext
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from debconf_translation_manager.services.template_parser import get_mock_templates
from debconf_translation_manager.widgets.filter_bar import FilterBar
from debconf_translation_manager.widgets.status_badge import StatusBadge

_ = gettext.gettext


class TemplateBrowserView(Gtk.Box):
    """Browse and search debconf templates from packages."""

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._templates = get_mock_templates()
        self._filtered: list[dict[str, Any]] = list(self._templates)
        self._build_ui()
        self._populate()

    def focus_search(self) -> None:
        self._filter_bar.focus_search()

    def get_export_data(self) -> list[dict[str, Any]]:
        return [
            {
                "package": t["package"],
                "template": t["template_name"],
                "type": t["template_type"],
                "priority": t["priority"],
                "description": t["description"],
            }
            for t in self._filtered
        ]

    def _build_ui(self) -> None:
        # Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.set_margin_start(16)
        title_box.set_margin_top(12)
        title_box.set_margin_bottom(4)
        title = Gtk.Label(label=_("Template Browser"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title_box.append(title)

        self._count_label = Gtk.Label()
        self._count_label.add_css_class("dim-label")
        self._count_label.set_halign(Gtk.Align.START)
        title_box.append(self._count_label)
        self.append(title_box)

        # Filter bar
        type_options = ["All Types", "select", "multiselect", "string",
                        "boolean", "note", "text", "password"]
        priority_options = ["All Priorities", "critical", "high", "medium", "low"]

        self._filter_bar = FilterBar(
            search_placeholder=_("Search templates…"),
            filters=[
                (_("Type"), type_options),
                (_("Priority"), priority_options),
            ],
            on_changed=self._apply_filters,
        )
        self.append(self._filter_bar)
        self.append(Gtk.Separator())

        # Template list
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

        self._detail_desc = Gtk.Label(xalign=0, wrap=True)
        box.append(self._detail_desc)

        self._detail_ext = Gtk.Label(xalign=0, wrap=True)
        self._detail_ext.add_css_class("body")
        box.append(self._detail_ext)

        self._detail_choices = Gtk.Label(xalign=0, wrap=True)
        self._detail_choices.add_css_class("monospace")
        box.append(self._detail_choices)

        frame.set_child(box)
        return frame

    def _populate(self) -> None:
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = self._filter_bar.search_text
        type_filter = self._filter_bar.get_filter_value(_("Type"))
        priority_filter = self._filter_bar.get_filter_value(_("Priority"))

        self._filtered = []
        for t in self._templates:
            if query and query not in t["template_name"].lower() and query not in t["description"].lower() and query not in t["package"].lower():
                continue
            if type_filter and not type_filter.startswith("All") and t["template_type"] != type_filter:
                continue
            if priority_filter and not priority_filter.startswith("All") and t["priority"] != priority_filter:
                continue
            self._filtered.append(t)

        self._rebuild_list()

    def _rebuild_list(self) -> None:
        # Clear existing
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        for t in self._filtered:
            row = self._make_template_row(t)
            self._list_box.append(row)

        self._count_label.set_label(f"({len(self._filtered)})")
        self._detail_revealer.set_reveal_child(False)

    def _make_template_row(self, t: dict[str, Any]) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._template = t

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        # Left: package + template
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)

        name = Gtk.Label(label=t["template_name"], xalign=0)
        name.add_css_class("heading")
        name.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        left.append(name)

        desc = Gtk.Label(label=t["description"], xalign=0)
        desc.add_css_class("dim-label")
        desc.set_ellipsize(3)
        left.append(desc)

        box.append(left)

        # Right: type badge + priority
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right.set_valign(Gtk.Align.CENTER)

        type_lbl = Gtk.Label(label=t["template_type"])
        type_lbl.add_css_class("caption")
        type_lbl.add_css_class("accent")
        right.append(type_lbl)

        prio_lbl = Gtk.Label(label=t["priority"])
        prio_lbl.add_css_class("caption")
        if t["priority"] == "critical":
            prio_lbl.add_css_class("error")
        elif t["priority"] == "high":
            prio_lbl.add_css_class("warning")
        right.append(prio_lbl)

        box.append(right)
        row.set_child(box)
        return row

    def _on_row_selected(
        self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None
    ) -> None:
        if row is None:
            self._detail_revealer.set_reveal_child(False)
            return

        t = row._template
        self._detail_title.set_label(t["template_name"])
        self._detail_info.set_label(
            f"{_('Package')}: {t['package']}  |  "
            f"{_('Type')}: {t['template_type']}  |  "
            f"{_('Priority')}: {t['priority']}  |  "
            f"{_('Default')}: {t.get('default', '')}"
        )
        self._detail_desc.set_label(t["description"])
        self._detail_ext.set_label(t.get("extended_description", ""))
        choices = t.get("choices", [])
        if choices:
            self._detail_choices.set_label(
                _("Choices: ") + ", ".join(choices)
            )
            self._detail_choices.set_visible(True)
        else:
            self._detail_choices.set_visible(False)

        self._detail_revealer.set_reveal_child(True)
