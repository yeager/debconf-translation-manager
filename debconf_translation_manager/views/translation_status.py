"""Translation Status view — per-language coverage dashboard."""

from __future__ import annotations

import gettext
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from debconf_translation_manager.services.l10n_debian import get_mock_l10n_data
from debconf_translation_manager.services.template_parser import (
    get_mock_po_entries,
    get_mock_templates,
)
from debconf_translation_manager.widgets.filter_bar import FilterBar
from debconf_translation_manager.widgets.status_badge import StatusBadge

_ = gettext.gettext

_LANGUAGES = [
    "sv", "de", "fr", "es", "pt_BR", "ja", "zh_CN", "ru", "it", "nl",
    "pl", "cs", "da", "fi", "nb", "ko", "el", "hu", "ca", "uk",
]


class TranslationStatusView(Gtk.Box):
    """Per-language translation coverage dashboard."""

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._language = "sv"
        self._build_ui()
        self._refresh()

    def focus_search(self) -> None:
        self._filter_bar.focus_search()

    def get_export_data(self) -> list[dict[str, Any]]:
        return self._export_data

    def _build_ui(self) -> None:
        # Title
        title = Gtk.Label(label=_("Translation Status"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_margin_start(16)
        title.set_margin_top(12)
        title.set_margin_bottom(4)
        self.append(title)

        # Filter bar with language selector
        self._filter_bar = FilterBar(
            search_placeholder=_("Filter packages…"),
            filters=[
                (_("Language"), _LANGUAGES),
                (_("Status"), ["All", "translated", "untranslated", "fuzzy", "pending-review"]),
            ],
            on_changed=self._on_filter_changed,
        )
        self.append(self._filter_bar)

        # Summary cards
        self._summary_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=12
        )
        self._summary_box.set_margin_start(16)
        self._summary_box.set_margin_end(16)
        self._summary_box.set_margin_top(8)
        self._summary_box.set_margin_bottom(8)
        self._summary_box.set_homogeneous(True)

        self._card_total = self._make_stat_card(_("Total"), "0")
        self._card_translated = self._make_stat_card(_("Translated"), "0")
        self._card_fuzzy = self._make_stat_card(_("Fuzzy"), "0")
        self._card_untranslated = self._make_stat_card(_("Untranslated"), "0")
        self._card_coverage = self._make_stat_card(_("Coverage"), "0%")

        self._summary_box.append(self._card_total)
        self._summary_box.append(self._card_translated)
        self._summary_box.append(self._card_fuzzy)
        self._summary_box.append(self._card_untranslated)
        self._summary_box.append(self._card_coverage)
        self.append(self._summary_box)

        # Progress bar
        self._progress = Gtk.ProgressBar()
        self._progress.set_margin_start(16)
        self._progress.set_margin_end(16)
        self._progress.set_margin_bottom(8)
        self._progress.set_show_text(True)
        self.append(self._progress)

        self.append(Gtk.Separator())

        # Package status list
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(16)
        self._list_box.set_margin_end(16)
        self._list_box.set_margin_top(8)
        self._list_box.set_margin_bottom(8)

        scroll.set_child(self._list_box)
        self.append(scroll)

    def _make_stat_card(self, title: str, value: str) -> Gtk.Frame:
        frame = Gtk.Frame()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_halign(Gtk.Align.CENTER)

        val_label = Gtk.Label(label=value)
        val_label.add_css_class("title-1")
        box.append(val_label)

        ttl_label = Gtk.Label(label=title)
        ttl_label.add_css_class("caption")
        ttl_label.add_css_class("dim-label")
        box.append(ttl_label)

        frame.set_child(box)
        frame._value_label = val_label
        return frame

    def _on_filter_changed(self) -> None:
        lang = self._filter_bar.get_filter_value(_("Language"))
        if lang and lang != self._language:
            self._language = lang
        self._refresh()

    def _refresh(self) -> None:
        data = get_mock_l10n_data(self._language)
        query = self._filter_bar.search_text
        status_filter = self._filter_bar.get_filter_value(_("Status"))

        filtered = []
        for pkg in data:
            if query and query not in pkg.package.lower():
                continue
            if status_filter and status_filter != "All" and pkg.status != status_filter:
                continue
            filtered.append(pkg)

        # Compute stats
        total = len(data)
        translated = sum(1 for p in data if p.status == "translated")
        fuzzy = sum(1 for p in data if p.status == "fuzzy")
        untranslated = sum(1 for p in data if p.status == "untranslated")
        coverage = (translated / total * 100) if total else 0

        self._card_total._value_label.set_label(str(total))
        self._card_translated._value_label.set_label(str(translated))
        self._card_fuzzy._value_label.set_label(str(fuzzy))
        self._card_untranslated._value_label.set_label(str(untranslated))
        self._card_coverage._value_label.set_label(f"{coverage:.0f}%")

        self._progress.set_fraction(coverage / 100)
        self._progress.set_text(f"{coverage:.1f}% ({translated}/{total})")

        # Populate list
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        self._export_data = []
        for pkg in filtered:
            row = self._make_status_row(pkg)
            self._list_box.append(row)
            self._export_data.append({
                "package": pkg.package,
                "status": pkg.status,
                "language": pkg.language,
                "translator": pkg.translator,
                "reviewer": pkg.reviewer,
                "date": pkg.date,
                "score": pkg.score,
            })

    def _make_status_row(self, pkg: Any) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        # Package name
        name = Gtk.Label(label=pkg.package, xalign=0)
        name.add_css_class("heading")
        name.set_hexpand(True)
        box.append(name)

        # Translator
        if pkg.translator:
            tr = Gtk.Label(label=pkg.translator)
            tr.add_css_class("dim-label")
            box.append(tr)

        # Score
        score_label = Gtk.Label(label=f"{pkg.score}%")
        score_label.add_css_class("caption")
        box.append(score_label)

        # Status badge
        badge = StatusBadge(status=pkg.status)
        box.append(badge)

        row.set_child(box)
        return row
