"""Reusable filter bar with search entry and dropdown filters."""

from __future__ import annotations

import gettext
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

_ = gettext.gettext


class FilterBar(Gtk.Box):
    """A horizontal bar with a search entry and optional dropdown filters."""

    def __init__(
        self,
        search_placeholder: str = "",
        filters: list[tuple[str, list[str]]] | None = None,
        on_changed: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            **kwargs,
        )
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.set_margin_bottom(4)

        self._on_changed = on_changed
        self._dropdowns: dict[str, Gtk.DropDown] = {}

        # Search entry
        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text(search_placeholder or _("Search…"))
        self._search.set_hexpand(True)
        self._search.connect("search-changed", self._emit_changed)
        self.append(self._search)

        # Optional dropdown filters
        if filters:
            for label, options in filters:
                self._add_dropdown(label, options)

    @property
    def search_text(self) -> str:
        return self._search.get_text().strip().lower()

    def focus_search(self) -> None:
        self._search.grab_focus()

    def get_filter_value(self, label: str) -> str:
        dd = self._dropdowns.get(label)
        if dd is None:
            return ""
        idx = dd.get_selected()
        model = dd.get_model()
        if model is None or idx == Gtk.INVALID_LIST_POSITION:
            return ""
        return model.get_string(idx) or ""

    def _add_dropdown(self, label: str, options: list[str]) -> None:
        lbl = Gtk.Label(label=label)
        lbl.add_css_class("dim-label")
        self.append(lbl)

        model = Gtk.StringList.new(options)
        dd = Gtk.DropDown(model=model)
        dd.set_selected(0)
        dd.connect("notify::selected", self._emit_changed)
        self.append(dd)
        self._dropdowns[label] = dd

    def _emit_changed(self, *args) -> None:
        if self._on_changed:
            self._on_changed()
