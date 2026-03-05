"""Review Board view — pull data from l10n.debian.org, show packages
needing review, pending translations, coordinator info."""

from __future__ import annotations

import gettext
import logging
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from debconf_translation_manager.services.l10n_debian import (
    L10nPackageStatus,
    fetch_and_parse,
)
from debconf_translation_manager.widgets.filter_bar import FilterBar
from debconf_translation_manager.widgets.status_badge import StatusBadge

_ = gettext.gettext
log = logging.getLogger(__name__)


class ReviewBoardView(Gtk.Box):
    """Review board pulling data from l10n.debian.org coordination pages.

    Displays packages needing review, pending translations, and
    coordinator / translator info.  Supports live fetch from
    l10n.debian.org or fallback to mock data.
    """

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._language = "sv"
        self._data: list[L10nPackageStatus] = []
        self._filtered: list[L10nPackageStatus] = []
        self._build_ui()
        self._load_data(use_network=False)

    # -- public interface -----------------------------------------------

    def focus_search(self) -> None:
        self._filter_bar.focus_search()

    def get_export_data(self) -> list[dict[str, Any]]:
        return [
            {
                "package": p.package,
                "status": p.status,
                "language": p.language,
                "translator": p.translator,
                "reviewer": p.reviewer,
                "date": p.date,
                "deadline": p.deadline,
                "score": p.score,
            }
            for p in self._filtered
        ]

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        # Title row
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_row.set_margin_start(16)
        title_row.set_margin_end(16)
        title_row.set_margin_top(12)
        title_row.set_margin_bottom(4)

        title = Gtk.Label(label=_("Review Board"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        title_row.append(title)

        # Refresh button — network fetch
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh from l10n.debian.org"))
        refresh_btn.connect("clicked", self._on_refresh)
        title_row.append(refresh_btn)

        self._spinner = Gtk.Spinner()
        title_row.append(self._spinner)

        self.append(title_row)

        # Source URL info
        url_label = Gtk.Label(
            label=_("Source: https://l10n.debian.org/coordination/{lang}/{lang}.by_status.html").format(
                lang=self._language
            ),
            xalign=0,
        )
        url_label.add_css_class("caption")
        url_label.add_css_class("dim-label")
        url_label.set_margin_start(16)
        url_label.set_selectable(True)
        self._url_label = url_label
        self.append(url_label)

        # Filter bar
        self._filter_bar = FilterBar(
            search_placeholder=_("Filter packages…"),
            filters=[
                (_("Status"), [
                    "All",
                    "pending-review",
                    "translated",
                    "fuzzy",
                    "untranslated",
                ]),
                (_("Language"), [
                    "sv", "de", "fr", "es", "pt_BR", "ja", "zh_CN",
                    "ru", "it", "nl", "da", "fi", "nb", "pl",
                ]),
            ],
            on_changed=self._apply_filters,
        )
        self.append(self._filter_bar)

        # Summary cards row
        cards = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        cards.set_margin_start(16)
        cards.set_margin_end(16)
        cards.set_margin_top(8)
        cards.set_margin_bottom(4)
        cards.set_homogeneous(True)

        self._card_review = self._make_card(_("Needs Review"), "0", "warning")
        self._card_translated = self._make_card(_("Translated"), "0", "success")
        self._card_fuzzy = self._make_card(_("Fuzzy"), "0", "accent")
        self._card_untranslated = self._make_card(_("Untranslated"), "0", "error")
        cards.append(self._card_review)
        cards.append(self._card_translated)
        cards.append(self._card_fuzzy)
        cards.append(self._card_untranslated)
        self.append(cards)

        self.append(Gtk.Separator())

        # Main list
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

        # Detail panel (shown when a row is selected)
        self._detail_revealer = Gtk.Revealer()
        self._detail_revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_UP
        )
        self._detail_box = self._build_detail_panel()
        self._detail_revealer.set_child(self._detail_box)
        self.append(self._detail_revealer)

    def _build_detail_panel(self) -> Gtk.Frame:
        frame = Gtk.Frame()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        self._det_title = Gtk.Label(xalign=0)
        self._det_title.add_css_class("title-4")
        box.append(self._det_title)

        # Info grid
        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(16)

        labels = [
            (_("Status:"), "_det_status"),
            (_("Translator:"), "_det_translator"),
            (_("Reviewer:"), "_det_reviewer"),
            (_("Date:"), "_det_date"),
            (_("Deadline:"), "_det_deadline"),
            (_("Score:"), "_det_score"),
        ]
        for i, (text, attr) in enumerate(labels):
            key = Gtk.Label(label=text, xalign=0)
            key.add_css_class("dim-label")
            grid.attach(key, 0, i, 1, 1)
            val = Gtk.Label(xalign=0)
            val.set_selectable(True)
            grid.attach(val, 1, i, 1, 1)
            setattr(self, attr, val)

        box.append(grid)

        # Action buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(8)

        open_web_btn = Gtk.Button(label=_("Open on l10n.debian.org"))
        open_web_btn.connect("clicked", self._on_open_web)
        btn_box.append(open_web_btn)

        self._claim_btn = Gtk.Button(label=_("Claim for Review"))
        self._claim_btn.add_css_class("suggested-action")
        self._claim_btn.connect("clicked", self._on_claim)
        btn_box.append(self._claim_btn)

        box.append(btn_box)
        frame.set_child(box)
        return frame

    def _make_card(self, title: str, value: str, css_class: str) -> Gtk.Frame:
        frame = Gtk.Frame()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_halign(Gtk.Align.CENTER)

        val = Gtk.Label(label=value)
        val.add_css_class("title-1")
        val.add_css_class(css_class)
        box.append(val)

        lbl = Gtk.Label(label=title)
        lbl.add_css_class("caption")
        lbl.add_css_class("dim-label")
        box.append(lbl)

        frame.set_child(box)
        frame._value_label = val
        return frame

    # -- data loading ---------------------------------------------------

    def _load_data(self, use_network: bool = False) -> None:
        if use_network:
            self._spinner.start()
            # Run network fetch in a thread to avoid blocking UI
            Gio.Task.new(None, None, self._on_fetch_done).run_in_thread(
                self._fetch_thread
            )
        else:
            self._data = fetch_and_parse(self._language)
            self._apply_filters()

    def _fetch_thread(self, task: Gio.Task, source: None, data: None, cancellable: None) -> None:
        """Runs in a worker thread."""
        try:
            result = fetch_and_parse(self._language, "status")
            task.return_value(result)
        except Exception as exc:
            log.warning("Fetch failed: %s", exc)
            task.return_value(fetch_and_parse(self._language))

    def _on_fetch_done(self, source: None, result: Gio.AsyncResult) -> None:
        self._spinner.stop()
        task = result
        if hasattr(task, "propagate_value"):
            data = task.propagate_value()
            if data:
                self._data = data
        else:
            self._data = fetch_and_parse(self._language)
        self._apply_filters()
        if self._window:
            self._window.show_toast(
                _("Loaded %d packages from l10n.debian.org") % len(self._data)
            )

    # -- filtering & display -------------------------------------------

    def _apply_filters(self) -> None:
        # Check if language changed
        lang = self._filter_bar.get_filter_value(_("Language"))
        if lang and lang != self._language:
            self._language = lang
            self._url_label.set_label(
                _("Source: https://l10n.debian.org/coordination/{lang}/{lang}.by_status.html").format(
                    lang=self._language
                )
            )
            self._data = fetch_and_parse(self._language)

        query = self._filter_bar.search_text
        status_filter = self._filter_bar.get_filter_value(_("Status"))

        self._filtered = []
        for pkg in self._data:
            if query and query not in pkg.package.lower():
                continue
            if status_filter and status_filter != "All" and pkg.status != status_filter:
                continue
            self._filtered.append(pkg)

        self._update_cards()
        self._rebuild_list()

    def _update_cards(self) -> None:
        review = sum(1 for p in self._data if p.status == "pending-review")
        translated = sum(1 for p in self._data if p.status == "translated")
        fuzzy = sum(1 for p in self._data if p.status == "fuzzy")
        untranslated = sum(1 for p in self._data if p.status == "untranslated")

        self._card_review._value_label.set_label(str(review))
        self._card_translated._value_label.set_label(str(translated))
        self._card_fuzzy._value_label.set_label(str(fuzzy))
        self._card_untranslated._value_label.set_label(str(untranslated))

    def _rebuild_list(self) -> None:
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        # Sort: pending-review first, then fuzzy, untranslated, translated
        order = {"pending-review": 0, "fuzzy": 1, "untranslated": 2, "translated": 3}
        sorted_data = sorted(self._filtered, key=lambda p: (order.get(p.status, 9), p.package))

        for pkg in sorted_data:
            row = self._make_row(pkg)
            self._list_box.append(row)

        self._detail_revealer.set_reveal_child(False)

    def _make_row(self, pkg: L10nPackageStatus) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._pkg = pkg

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        # Left column
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)

        name = Gtk.Label(label=pkg.package, xalign=0)
        name.add_css_class("heading")
        left.append(name)

        info_parts = []
        if pkg.translator:
            info_parts.append(_("Translator: %s") % pkg.translator)
        if pkg.reviewer:
            info_parts.append(_("Reviewer: %s") % pkg.reviewer)
        if pkg.deadline:
            info_parts.append(_("Deadline: %s") % pkg.deadline)
        if info_parts:
            info = Gtk.Label(label=" · ".join(info_parts), xalign=0)
            info.add_css_class("caption")
            info.add_css_class("dim-label")
            info.set_ellipsize(3)
            left.append(info)

        box.append(left)

        # Right: score + status
        if pkg.score > 0:
            score = Gtk.Label(label=f"{pkg.score}%")
            score.add_css_class("caption")
            box.append(score)

        badge = StatusBadge(status=pkg.status)
        box.append(badge)

        row.set_child(box)
        return row

    # -- callbacks ------------------------------------------------------

    def _on_row_selected(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            self._detail_revealer.set_reveal_child(False)
            return

        pkg = row._pkg
        self._det_title.set_label(pkg.package)
        self._det_status.set_label(pkg.status)
        self._det_translator.set_label(pkg.translator or _("(none)"))
        self._det_reviewer.set_label(pkg.reviewer or _("(none)"))
        self._det_date.set_label(pkg.date or _("(unknown)"))
        self._det_deadline.set_label(pkg.deadline or _("(none)"))
        self._det_score.set_label(f"{pkg.score}%")
        self._detail_revealer.set_reveal_child(True)

    def _on_refresh(self, btn: Gtk.Button) -> None:
        self._load_data(use_network=True)

    def _on_open_web(self, btn: Gtk.Button) -> None:
        url = f"https://l10n.debian.org/coordination/{self._language}/{self._language}.by_status.html"
        Gtk.show_uri(self._window, url, 0)

    def _on_claim(self, btn: Gtk.Button) -> None:
        if self._window:
            self._window.show_toast(_("Claim functionality requires l10n.debian.org authentication"))
