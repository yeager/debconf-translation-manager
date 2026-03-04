"""Statistics view — charts/graphs of translation coverage using Cairo."""

from __future__ import annotations

import gettext
import math
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk

from debconf_translation_manager.services.l10n_debian import get_mock_l10n_data

_ = gettext.gettext

# Colour palette for charts (R, G, B)
_COLORS = [
    (0.27, 0.63, 0.83),   # blue
    (0.36, 0.72, 0.36),   # green
    (0.91, 0.73, 0.27),   # amber
    (0.83, 0.33, 0.33),   # red
    (0.60, 0.40, 0.80),   # purple
    (0.20, 0.70, 0.65),   # teal
    (0.90, 0.50, 0.20),   # orange
]


class StatisticsView(Gtk.Box):
    """Translation coverage statistics with Cairo-drawn charts."""

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._language = "sv"
        self._build_ui()
        self._refresh_data()

    def focus_search(self) -> None:
        pass  # No search in stats view

    def get_export_data(self) -> list[dict[str, Any]]:
        return self._export_data

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        # Title
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_row.set_margin_start(16)
        title_row.set_margin_end(16)
        title_row.set_margin_top(12)
        title_row.set_margin_bottom(4)

        title = Gtk.Label(label=_("Statistics"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        title_row.append(title)

        # Language selector
        lang_label = Gtk.Label(label=_("Language:"))
        lang_label.add_css_class("dim-label")
        title_row.append(lang_label)

        langs = ["sv", "de", "fr", "es", "pt_BR", "ja", "zh_CN", "ru", "it", "nl", "da", "fi", "nb"]
        lang_model = Gtk.StringList.new(langs)
        self._lang_dd = Gtk.DropDown(model=lang_model)
        self._lang_dd.set_selected(0)
        self._lang_dd.connect("notify::selected", self._on_lang_changed)
        title_row.append(self._lang_dd)

        self.append(title_row)
        self.append(Gtk.Separator())

        # Scrollable content
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)

        # ---- Overview cards ----
        self._cards_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._cards_box.set_homogeneous(True)

        self._card_total = self._make_stat_card(_("Total Packages"), "0")
        self._card_coverage = self._make_stat_card(_("Coverage"), "0%")
        self._card_complete = self._make_stat_card(_("Complete"), "0")
        self._card_needs_work = self._make_stat_card(_("Needs Work"), "0")

        self._cards_box.append(self._card_total)
        self._cards_box.append(self._card_coverage)
        self._cards_box.append(self._card_complete)
        self._cards_box.append(self._card_needs_work)
        content.append(self._cards_box)

        # ---- Pie chart: status distribution ----
        pie_frame = Gtk.Frame()
        pie_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        pie_box.set_margin_start(16)
        pie_box.set_margin_end(16)
        pie_box.set_margin_top(12)
        pie_box.set_margin_bottom(12)

        pie_title = Gtk.Label(label=_("Status Distribution"), xalign=0)
        pie_title.add_css_class("title-4")
        pie_box.append(pie_title)

        pie_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

        self._pie_area = Gtk.DrawingArea()
        self._pie_area.set_size_request(220, 220)
        self._pie_area.set_draw_func(self._draw_pie)
        pie_row.append(self._pie_area)

        self._pie_legend = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._pie_legend.set_valign(Gtk.Align.CENTER)
        pie_row.append(self._pie_legend)

        pie_box.append(pie_row)
        pie_frame.set_child(pie_box)
        content.append(pie_frame)

        # ---- Bar chart: per-package score ----
        bar_frame = Gtk.Frame()
        bar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        bar_box.set_margin_start(16)
        bar_box.set_margin_end(16)
        bar_box.set_margin_top(12)
        bar_box.set_margin_bottom(12)

        bar_title = Gtk.Label(label=_("Per-Package Score"), xalign=0)
        bar_title.add_css_class("title-4")
        bar_box.append(bar_title)

        self._bar_area = Gtk.DrawingArea()
        self._bar_area.set_size_request(-1, 300)
        self._bar_area.set_draw_func(self._draw_bars)
        self._bar_area.set_hexpand(True)
        bar_box.append(self._bar_area)

        bar_frame.set_child(bar_box)
        content.append(bar_frame)

        # ---- Multi-language comparison bar chart ----
        cmp_frame = Gtk.Frame()
        cmp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        cmp_box.set_margin_start(16)
        cmp_box.set_margin_end(16)
        cmp_box.set_margin_top(12)
        cmp_box.set_margin_bottom(12)

        cmp_title = Gtk.Label(label=_("Cross-Language Coverage"), xalign=0)
        cmp_title.add_css_class("title-4")
        cmp_box.append(cmp_title)

        self._cmp_area = Gtk.DrawingArea()
        self._cmp_area.set_size_request(-1, 250)
        self._cmp_area.set_draw_func(self._draw_lang_comparison)
        self._cmp_area.set_hexpand(True)
        cmp_box.append(self._cmp_area)

        cmp_frame.set_child(cmp_box)
        content.append(cmp_frame)

        # ---- Coverage timeline (simulated) ----
        timeline_frame = Gtk.Frame()
        timeline_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        timeline_box.set_margin_start(16)
        timeline_box.set_margin_end(16)
        timeline_box.set_margin_top(12)
        timeline_box.set_margin_bottom(12)

        timeline_title = Gtk.Label(label=_("Coverage Over Time (simulated)"), xalign=0)
        timeline_title.add_css_class("title-4")
        timeline_box.append(timeline_title)

        self._timeline_area = Gtk.DrawingArea()
        self._timeline_area.set_size_request(-1, 200)
        self._timeline_area.set_draw_func(self._draw_timeline)
        self._timeline_area.set_hexpand(True)
        timeline_box.append(self._timeline_area)

        timeline_frame.set_child(timeline_box)
        content.append(timeline_frame)

        scroll.set_child(content)
        self.append(scroll)

    def _make_stat_card(self, title: str, value: str) -> Gtk.Frame:
        frame = Gtk.Frame()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_halign(Gtk.Align.CENTER)

        val = Gtk.Label(label=value)
        val.add_css_class("title-1")
        box.append(val)

        ttl = Gtk.Label(label=title)
        ttl.add_css_class("caption")
        ttl.add_css_class("dim-label")
        box.append(ttl)

        frame.set_child(box)
        frame._value_label = val
        return frame

    # -- data -----------------------------------------------------------

    def _refresh_data(self) -> None:
        data = get_mock_l10n_data(self._language)

        total = len(data)
        translated = sum(1 for p in data if p.status == "translated")
        fuzzy = sum(1 for p in data if p.status == "fuzzy")
        untranslated = sum(1 for p in data if p.status == "untranslated")
        pending = sum(1 for p in data if p.status == "pending-review")
        coverage = (translated / total * 100) if total else 0

        self._card_total._value_label.set_label(str(total))
        self._card_coverage._value_label.set_label(f"{coverage:.0f}%")
        self._card_complete._value_label.set_label(str(translated))
        self._card_needs_work._value_label.set_label(str(fuzzy + untranslated))

        # Data for charts
        self._pie_data = {
            _("Translated"): translated,
            _("Fuzzy"): fuzzy,
            _("Untranslated"): untranslated,
            _("Pending Review"): pending,
        }

        self._bar_data = [(p.package, p.score) for p in sorted(data, key=lambda p: -p.score)]

        # Cross-language coverage simulation
        self._lang_coverage = {}
        for lang in ["sv", "de", "fr", "es", "pt_BR", "ja", "ru", "it"]:
            ldata = get_mock_l10n_data(lang)
            t = sum(1 for p in ldata if p.status == "translated")
            self._lang_coverage[lang] = (t / len(ldata) * 100) if ldata else 0

        # Simulated timeline data (monthly coverage %)
        self._timeline_data = [
            ("2025-07", 20), ("2025-08", 25), ("2025-09", 30),
            ("2025-10", 38), ("2025-11", 42), ("2025-12", 48),
            ("2026-01", 55), ("2026-02", 60), ("2026-03", coverage),
        ]

        # Rebuild legend
        while True:
            child = self._pie_legend.get_first_child()
            if child is None:
                break
            self._pie_legend.remove(child)

        for i, (label, count) in enumerate(self._pie_data.items()):
            r, g, b = _COLORS[i % len(_COLORS)]
            legend_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

            swatch = Gtk.DrawingArea()
            swatch.set_size_request(14, 14)
            swatch.set_draw_func(self._make_swatch_draw(r, g, b))
            legend_row.append(swatch)

            lbl = Gtk.Label(label=f"{label}: {count}")
            lbl.set_xalign(0)
            legend_row.append(lbl)

            self._pie_legend.append(legend_row)

        # Export data
        self._export_data = [
            {"package": p, "score": s, "language": self._language}
            for p, s in self._bar_data
        ]

        # Force redraw
        self._pie_area.queue_draw()
        self._bar_area.queue_draw()
        self._cmp_area.queue_draw()
        self._timeline_area.queue_draw()

    def _on_lang_changed(self, dd: Gtk.DropDown, param_args: Any) -> None:
        model = dd.get_model()
        idx = dd.get_selected()
        if model and idx != 0xFFFFFFFF:
            self._language = model.get_string(idx) or "sv"
            self._refresh_data()

    # -- Cairo drawing callbacks ----------------------------------------

    def _make_swatch_draw(self, r: float, g: float, b: float):
        def draw(area: Gtk.DrawingArea, cr, w: int, h: int) -> None:
            cr.set_source_rgb(r, g, b)
            cr.rectangle(0, 0, w, h)
            cr.fill()
        return draw

    def _draw_pie(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        total = sum(self._pie_data.values())
        if total == 0:
            return

        cx, cy = width / 2, height / 2
        radius = min(cx, cy) - 10
        start_angle = -math.pi / 2

        for i, (label, count) in enumerate(self._pie_data.items()):
            if count == 0:
                continue
            sweep = 2 * math.pi * count / total
            r, g, b = _COLORS[i % len(_COLORS)]
            cr.set_source_rgb(r, g, b)
            cr.move_to(cx, cy)
            cr.arc(cx, cy, radius, start_angle, start_angle + sweep)
            cr.close_path()
            cr.fill()
            start_angle += sweep

        # Center circle (donut)
        style = area.get_style_context()
        # Use a neutral grey that works in both themes
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.15)
        cr.arc(cx, cy, radius * 0.55, 0, 2 * math.pi)
        cr.fill()

        # Coverage text in center
        coverage = self._pie_data.get(_("Translated"), 0) / total * 100 if total else 0
        cr.set_source_rgb(0.6, 0.6, 0.6)
        cr.select_font_face("Sans", 0, 1)  # NORMAL, BOLD
        cr.set_font_size(20)
        text = f"{coverage:.0f}%"
        extents = cr.text_extents(text)
        cr.move_to(cx - extents.width / 2, cy + extents.height / 2)
        cr.show_text(text)

    def _draw_bars(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        if not self._bar_data:
            return

        n = len(self._bar_data)
        margin_left = 120
        margin_right = 20
        margin_top = 10
        margin_bottom = 10
        bar_area_w = width - margin_left - margin_right
        bar_h = max(4, (height - margin_top - margin_bottom) / n - 4)

        for i, (pkg, score) in enumerate(self._bar_data):
            y = margin_top + i * (bar_h + 4)
            bar_w = bar_area_w * score / 100

            # Colour by score
            if score >= 90:
                cr.set_source_rgb(0.36, 0.72, 0.36)
            elif score >= 50:
                cr.set_source_rgb(0.91, 0.73, 0.27)
            else:
                cr.set_source_rgb(0.83, 0.33, 0.33)

            # Bar
            cr.rectangle(margin_left, y, bar_w, bar_h)
            cr.fill()

            # Background track
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.15)
            cr.rectangle(margin_left + bar_w, y, bar_area_w - bar_w, bar_h)
            cr.fill()

            # Package label
            cr.set_source_rgb(0.6, 0.6, 0.6)
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(11)
            cr.move_to(4, y + bar_h * 0.75)
            cr.show_text(pkg[:16])

            # Score label
            cr.move_to(margin_left + bar_w + 4, y + bar_h * 0.75)
            cr.show_text(f"{score}%")

    def _draw_lang_comparison(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        if not self._lang_coverage:
            return

        langs = sorted(self._lang_coverage.keys())
        n = len(langs)
        margin_left = 60
        margin_right = 20
        margin_top = 10
        margin_bottom = 30
        bar_area_w = width - margin_left - margin_right
        bar_w = max(8, bar_area_w / n - 8)
        chart_h = height - margin_top - margin_bottom

        for i, lang in enumerate(langs):
            coverage = self._lang_coverage[lang]
            x = margin_left + i * (bar_w + 8)
            bar_h = chart_h * coverage / 100

            # Color
            r, g, b = _COLORS[i % len(_COLORS)]
            cr.set_source_rgb(r, g, b)
            cr.rectangle(x, margin_top + chart_h - bar_h, bar_w, bar_h)
            cr.fill()

            # Background
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.1)
            cr.rectangle(x, margin_top, bar_w, chart_h - bar_h)
            cr.fill()

            # Language label
            cr.set_source_rgb(0.6, 0.6, 0.6)
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(10)
            cr.move_to(x + 2, height - 8)
            cr.show_text(lang)

            # Percentage on top
            cr.set_font_size(9)
            cr.move_to(x + 2, margin_top + chart_h - bar_h - 4)
            cr.show_text(f"{coverage:.0f}%")

        # Y axis labels
        cr.set_source_rgb(0.6, 0.6, 0.6)
        cr.set_font_size(10)
        for pct in (0, 25, 50, 75, 100):
            y = margin_top + chart_h - chart_h * pct / 100
            cr.move_to(4, y + 4)
            cr.show_text(f"{pct}%")
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.2)
            cr.move_to(margin_left, y)
            cr.line_to(width - margin_right, y)
            cr.stroke()
            cr.set_source_rgb(0.6, 0.6, 0.6)

    def _draw_timeline(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        if not self._timeline_data:
            return

        n = len(self._timeline_data)
        margin_left = 50
        margin_right = 20
        margin_top = 10
        margin_bottom = 30
        chart_w = width - margin_left - margin_right
        chart_h = height - margin_top - margin_bottom

        # Grid lines
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.2)
        for pct in (0, 25, 50, 75, 100):
            y = margin_top + chart_h - chart_h * pct / 100
            cr.move_to(margin_left, y)
            cr.line_to(width - margin_right, y)
            cr.stroke()

        # Y axis labels
        cr.set_source_rgb(0.6, 0.6, 0.6)
        cr.set_font_size(10)
        for pct in (0, 25, 50, 75, 100):
            y = margin_top + chart_h - chart_h * pct / 100
            cr.move_to(4, y + 4)
            cr.show_text(f"{pct}%")

        # Line + fill
        points = []
        for i, (month, pct) in enumerate(self._timeline_data):
            x = margin_left + chart_w * i / max(n - 1, 1)
            y = margin_top + chart_h - chart_h * pct / 100
            points.append((x, y))

        # Fill area under curve
        if points:
            cr.set_source_rgba(0.27, 0.63, 0.83, 0.2)
            cr.move_to(points[0][0], margin_top + chart_h)
            for x, y in points:
                cr.line_to(x, y)
            cr.line_to(points[-1][0], margin_top + chart_h)
            cr.close_path()
            cr.fill()

            # Line
            cr.set_source_rgb(0.27, 0.63, 0.83)
            cr.set_line_width(2.5)
            cr.move_to(*points[0])
            for x, y in points[1:]:
                cr.line_to(x, y)
            cr.stroke()

            # Dots
            for x, y in points:
                cr.arc(x, y, 4, 0, 2 * math.pi)
                cr.fill()

        # X axis labels
        cr.set_source_rgb(0.6, 0.6, 0.6)
        cr.set_font_size(9)
        for i, (month, pct) in enumerate(self._timeline_data):
            x = margin_left + chart_w * i / max(n - 1, 1)
            cr.move_to(x - 12, height - 6)
            cr.show_text(month)
