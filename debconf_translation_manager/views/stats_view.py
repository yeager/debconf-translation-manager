"""Statistics View — colorful charts showing translation progress."""

from __future__ import annotations

import gettext
import math
import threading
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

import cairo

from debconf_translation_manager.services.l10n_debian import (
    L10nPackageStatus,
    fetch_and_parse,
)
from debconf_translation_manager.services.settings import Settings

if TYPE_CHECKING:
    from debconf_translation_manager.window import MainWindow

_ = gettext.gettext

# Colors: green=translated, yellow=fuzzy, red=untranslated
COLOR_TRANSLATED = (0.298, 0.686, 0.314)     # #4CAF50
COLOR_FUZZY = (1.0, 0.757, 0.027)            # #FFC107
COLOR_UNTRANSLATED = (0.957, 0.263, 0.212)   # #F44336
COLOR_BG = (0.15, 0.15, 0.15)
COLOR_TEXT = (0.9, 0.9, 0.9)
COLOR_TEXT_DIM = (0.6, 0.6, 0.6)


class StatsView(Gtk.Box):
    """Statistics panel with pie and bar charts using Cairo."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window
        self._packages: list[L10nPackageStatus] = []
        self._total_translated = 0
        self._total_fuzzy = 0
        self._total_untranslated = 0
        self._build_ui()

    def _build_ui(self) -> None:
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label=_("Statistics")))

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh statistics"))
        refresh_btn.connect("clicked", lambda b: self.load_data())
        header.pack_end(refresh_btn)

        self.append(header)

        self._stack = Gtk.Stack()

        # Loading state
        self._status_page = Adw.StatusPage()
        self._status_page.set_title(_("Loading Statistics"))
        self._status_page.set_description(_("Fetching data…"))
        self._status_page.set_icon_name("emblem-synchronizing-symbolic")
        self._stack.add_named(self._status_page, "loading")

        # Chart content
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(16)
        content.set_margin_bottom(16)

        # Overall stats label
        self._overall_label = Gtk.Label(xalign=0)
        self._overall_label.add_css_class("title-3")
        content.append(self._overall_label)

        # Pie chart
        pie_frame = Gtk.Frame()
        pie_frame.set_margin_top(8)
        self._pie_area = Gtk.DrawingArea()
        self._pie_area.set_size_request(-1, 300)
        self._pie_area.set_draw_func(self._draw_pie)
        self._pie_area.add_css_class("chart-area")
        pie_frame.set_child(self._pie_area)
        content.append(pie_frame)

        # Bar chart: per-package breakdown (top 20 worst)
        bar_label = Gtk.Label(label=_("Packages needing most work"), xalign=0)
        bar_label.add_css_class("title-4")
        bar_label.set_margin_top(16)
        content.append(bar_label)

        bar_frame = Gtk.Frame()
        self._bar_area = Gtk.DrawingArea()
        self._bar_area.set_size_request(-1, 500)
        self._bar_area.set_draw_func(self._draw_bars)
        self._bar_area.add_css_class("chart-area")
        bar_frame.set_child(self._bar_area)
        content.append(bar_frame)

        # Summary stats group
        self._summary_group = Adw.PreferencesGroup()
        self._summary_group.set_title(_("Summary"))
        content.append(self._summary_group)

        scroll.set_child(content)
        self._stack.add_named(scroll, "charts")
        self._stack.set_visible_child_name("loading")

        self.append(self._stack)

    def load_data(self) -> None:
        self._stack.set_visible_child_name("loading")
        thread = threading.Thread(target=self._fetch_data, daemon=True)
        thread.start()

    def _fetch_data(self) -> None:
        lang = Settings.get().language_code
        packages = fetch_and_parse(lang)
        GLib.idle_add(self._on_data_loaded, packages)

    def _on_data_loaded(self, packages: list[L10nPackageStatus]) -> bool:
        self._packages = packages

        self._total_translated = sum(p.translated for p in packages)
        self._total_fuzzy = sum(p.fuzzy for p in packages)
        self._total_untranslated = sum(p.untranslated for p in packages)
        total_strings = self._total_translated + self._total_fuzzy + self._total_untranslated

        total_pkgs = len(packages)
        done_pkgs = sum(1 for p in packages if p.score == 100)
        pct = (done_pkgs / total_pkgs * 100) if total_pkgs else 0

        self._overall_label.set_label(
            _("%(done)d/%(total)d packages fully translated (%(pct).1f%%) — "
              "%(strings)d total strings") % {
                "done": done_pkgs,
                "total": total_pkgs,
                "pct": pct,
                "strings": total_strings,
            }
        )

        # Rebuild summary
        # Remove old rows by recreating group
        parent = self._summary_group.get_parent()
        if parent:
            parent.remove(self._summary_group)
        self._summary_group = Adw.PreferencesGroup()
        self._summary_group.set_title(_("Summary"))

        for title, value in [
            (_("Total Packages"), str(total_pkgs)),
            (_("Fully Translated"), str(done_pkgs)),
            (_("Partially Translated"), str(sum(1 for p in packages if 0 < p.score < 100))),
            (_("Not Started"), str(sum(1 for p in packages if p.score == 0))),
            (_("Total Translated Strings"), str(self._total_translated)),
            (_("Total Fuzzy Strings"), str(self._total_fuzzy)),
            (_("Total Untranslated Strings"), str(self._total_untranslated)),
        ]:
            row = Adw.ActionRow()
            row.set_title(title)
            row.set_subtitle(value)
            self._summary_group.add(row)

        if parent:
            parent.append(self._summary_group)

        # Redraw charts
        self._pie_area.queue_draw()
        self._bar_area.queue_draw()

        self._stack.set_visible_child_name("charts")
        return False

    def _draw_pie(self, area: Gtk.DrawingArea, cr: cairo.Context,
                  width: int, height: int) -> None:
        """Draw a pie chart of overall translation status."""
        total = self._total_translated + self._total_fuzzy + self._total_untranslated
        if total == 0:
            cr.set_source_rgb(*COLOR_TEXT_DIM)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(16)
            cr.move_to(width / 2 - 50, height / 2)
            cr.show_text(_("No data available"))
            return

        cx = width * 0.35
        cy = height / 2
        radius = min(cx, cy) - 30

        slices = [
            (self._total_translated / total, COLOR_TRANSLATED, _("Translated")),
            (self._total_fuzzy / total, COLOR_FUZZY, _("Fuzzy")),
            (self._total_untranslated / total, COLOR_UNTRANSLATED, _("Untranslated")),
        ]

        start_angle = -math.pi / 2
        for fraction, color, label in slices:
            if fraction <= 0:
                continue
            end_angle = start_angle + 2 * math.pi * fraction

            cr.set_source_rgb(*color)
            cr.move_to(cx, cy)
            cr.arc(cx, cy, radius, start_angle, end_angle)
            cr.close_path()
            cr.fill()

            # Outline
            cr.set_source_rgba(0, 0, 0, 0.3)
            cr.set_line_width(2)
            cr.move_to(cx, cy)
            cr.arc(cx, cy, radius, start_angle, end_angle)
            cr.close_path()
            cr.stroke()

            start_angle = end_angle

        # Legend
        legend_x = width * 0.65
        legend_y = height * 0.25
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(14)

        values = [self._total_translated, self._total_fuzzy, self._total_untranslated]
        for i, (fraction, color, label) in enumerate(slices):
            y = legend_y + i * 40

            # Color swatch
            cr.set_source_rgb(*color)
            cr.rectangle(legend_x, y, 20, 20)
            cr.fill()

            # Label
            cr.set_source_rgb(*COLOR_TEXT)
            cr.move_to(legend_x + 28, y + 15)
            pct = fraction * 100
            cr.show_text(f"{label}: {values[i]} ({pct:.1f}%)")

    def _draw_bars(self, area: Gtk.DrawingArea, cr: cairo.Context,
                   width: int, height: int) -> None:
        """Draw horizontal stacked bar chart for top packages needing work."""
        # Get worst packages (not 100%)
        pkgs = [p for p in self._packages if p.score < 100]
        pkgs.sort(key=lambda p: p.score)
        pkgs = pkgs[:20]  # Top 20 worst

        if not pkgs:
            cr.set_source_rgb(*COLOR_TEXT_DIM)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(16)
            cr.move_to(width / 2 - 50, height / 2)
            cr.show_text(_("All packages translated!"))
            return

        margin_left = 180
        margin_right = 20
        margin_top = 10
        bar_height = 20
        bar_spacing = 4
        bar_area_width = width - margin_left - margin_right

        # Resize drawing area to fit
        needed_height = margin_top + len(pkgs) * (bar_height + bar_spacing) + 10
        if needed_height > 500:
            self._bar_area.set_size_request(-1, needed_height)

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)

        for i, pkg in enumerate(pkgs):
            y = margin_top + i * (bar_height + bar_spacing)
            total = pkg.total if pkg.total > 0 else 1

            # Package name
            cr.set_source_rgb(*COLOR_TEXT)
            name = pkg.package
            if len(name) > 22:
                name = name[:20] + "…"
            cr.move_to(8, y + bar_height - 4)
            cr.show_text(name)

            # Stacked bar
            x = margin_left

            # Translated portion
            t_width = (pkg.translated / total) * bar_area_width
            if t_width > 0:
                cr.set_source_rgb(*COLOR_TRANSLATED)
                cr.rectangle(x, y, t_width, bar_height)
                cr.fill()
                x += t_width

            # Fuzzy portion
            f_width = (pkg.fuzzy / total) * bar_area_width
            if f_width > 0:
                cr.set_source_rgb(*COLOR_FUZZY)
                cr.rectangle(x, y, f_width, bar_height)
                cr.fill()
                x += f_width

            # Untranslated portion
            u_width = (pkg.untranslated / total) * bar_area_width
            if u_width > 0:
                cr.set_source_rgb(*COLOR_UNTRANSLATED)
                cr.rectangle(x, y, u_width, bar_height)
                cr.fill()

            # Percentage label
            cr.set_source_rgb(*COLOR_TEXT)
            cr.set_font_size(10)
            cr.move_to(margin_left + bar_area_width + 4, y + bar_height - 4)
            cr.show_text(f"{pkg.score}%")
            cr.set_font_size(11)
