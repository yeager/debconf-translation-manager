"""Statistics Page — overview of translation progress and history."""

from __future__ import annotations

import csv
import gettext
import io
import threading
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from debconf_translation_manager.services.l10n_debian import (
    fetch_and_parse,
    fetch_ranking_page,
    parse_ranking_html,
)
from debconf_translation_manager.services.settings import Settings
from debconf_translation_manager.services.submission_log import SubmissionLog

if TYPE_CHECKING:
    from debconf_translation_manager.window import MainWindow

_ = gettext.gettext


class StatsPage(Adw.NavigationPage):
    """Statistics and progress tracking page."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(title=_("Statistics"))
        self._window = window
        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()

        # Export CSV button
        export_btn = Gtk.Button(icon_name="document-save-as-symbolic")
        export_btn.set_tooltip_text(_("Export to CSV"))
        export_btn.connect("clicked", self._on_export_csv)
        header.pack_end(export_btn)

        # Refresh button
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh statistics"))
        refresh_btn.connect("clicked", self._on_refresh)
        header.pack_end(refresh_btn)

        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # Language overview group (populated on load)
        self._overview_group = Adw.PreferencesGroup()
        self._overview_group.set_title(_("Language Overview"))
        self._overview_group.set_description(_("Loading…"))
        self._content.append(self._overview_group)

        # Submission history group
        self._history_group = Adw.PreferencesGroup()
        self._history_group.set_title(_("Submission History"))
        self._content.append(self._history_group)

        # Ranking group
        self._ranking_group = Adw.PreferencesGroup()
        self._ranking_group.set_title(_("Language Rankings"))
        self._ranking_group.set_description(_("How your language compares to others"))
        self._content.append(self._ranking_group)

        # Progress timeline (ASCII-based)
        self._timeline_group = Adw.PreferencesGroup()
        self._timeline_group.set_title(_("Progress Timeline"))
        self._content.append(self._timeline_group)

        clamp.set_child(self._content)
        scroll.set_child(clamp)
        toolbar_view.set_content(scroll)
        self.set_child(toolbar_view)

    def load_data(self) -> None:
        """Fetch and display statistics."""
        thread = threading.Thread(target=self._fetch_all, daemon=True)
        thread.start()
        self._load_history()

    def _fetch_all(self) -> None:
        lang = Settings.get().language_code
        packages = fetch_and_parse(lang)

        ranking_html = fetch_ranking_page()
        rankings = parse_ranking_html(ranking_html) if ranking_html else []

        GLib.idle_add(self._update_overview, packages, rankings)

    def _update_overview(self, packages, rankings) -> bool:
        lang = Settings.get().language_code

        # Clear existing rows
        while True:
            child = self._overview_group.get_first_child()
            # PreferencesGroup has internal children, we need to use different approach
            break

        total = len(packages)
        translated = sum(1 for p in packages if p.score == 100)
        partial = sum(1 for p in packages if 0 < p.score < 100)
        untranslated = sum(1 for p in packages if p.score == 0)
        avg_score = sum(p.score for p in packages) / total if total else 0

        self._overview_group.set_description(
            _("%(lang)s: %(total)d packages total") % {"lang": lang, "total": total}
        )

        # Add stat rows (recreate group to clear)
        self._content.remove(self._overview_group)
        self._overview_group = Adw.PreferencesGroup()
        self._overview_group.set_title(_("Language Overview"))
        self._overview_group.set_description(
            _("%(lang)s: %(total)d packages total") % {"lang": lang, "total": total}
        )

        total_row = Adw.ActionRow()
        total_row.set_title(_("Total Packages"))
        total_row.set_subtitle(str(total))
        self._overview_group.add(total_row)

        done_row = Adw.ActionRow()
        done_row.set_title(_("Fully Translated"))
        done_row.set_subtitle(str(translated))
        self._overview_group.add(done_row)

        partial_row = Adw.ActionRow()
        partial_row.set_title(_("Partially Translated"))
        partial_row.set_subtitle(str(partial))
        self._overview_group.add(partial_row)

        untrans_row = Adw.ActionRow()
        untrans_row.set_title(_("Untranslated"))
        untrans_row.set_subtitle(str(untranslated))
        self._overview_group.add(untrans_row)

        avg_row = Adw.ActionRow()
        avg_row.set_title(_("Average Score"))
        avg_row.set_subtitle(f"{avg_score:.1f}%")
        self._overview_group.add(avg_row)

        pct = (translated / total * 100) if total else 0
        overall_row = Adw.ActionRow()
        overall_row.set_title(_("Overall Completion"))
        overall_row.set_subtitle(f"{pct:.1f}%")
        self._overview_group.add(overall_row)

        # Insert at beginning
        first = self._content.get_first_child()
        if first:
            self._content.insert_child_after(self._overview_group, None)
        else:
            self._content.append(self._overview_group)

        # Log stats snapshot
        SubmissionLog.get().log_stats_snapshot(lang, total, translated, pct)

        # Update rankings
        self._update_rankings(rankings, lang)

        # Update timeline
        self._update_timeline(lang)

        return False

    def _load_history(self) -> None:
        """Load submission history from database."""
        self._content.remove(self._history_group)
        self._history_group = Adw.PreferencesGroup()
        self._history_group.set_title(_("Submission History"))

        submissions = SubmissionLog.get().get_all_submissions()
        if not submissions:
            self._history_group.set_description(_("No submissions recorded yet"))
        else:
            self._history_group.set_description(
                _("%d submissions total") % len(submissions)
            )
            for record in submissions[:20]:
                row = Adw.ActionRow()
                row.set_title(record.package)
                row.set_subtitle(
                    f"{record.timestamp[:16]} — {record.translated}t/{record.fuzzy}f/{record.untranslated}u"
                )
                self._history_group.add(row)

        # Re-insert after overview
        overview = self._content.get_first_child()
        if overview:
            self._content.insert_child_after(self._history_group, overview)
        else:
            self._content.append(self._history_group)

    def _update_rankings(self, rankings: list, current_lang: str) -> None:
        self._content.remove(self._ranking_group)
        self._ranking_group = Adw.PreferencesGroup()
        self._ranking_group.set_title(_("Language Rankings"))

        if not rankings:
            self._ranking_group.set_description(_("Could not fetch ranking data"))
        else:
            for r in rankings[:15]:
                row = Adw.ActionRow()
                lang = r["language"]
                prefix = "→ " if lang == current_lang else ""
                row.set_title(f"{prefix}#{r['rank']} {lang}")
                row.set_subtitle(r["score"])
                if lang == current_lang:
                    row.add_css_class("accent")
                self._ranking_group.add(row)

        # Insert before timeline
        self._content.insert_child_after(
            self._ranking_group, self._history_group
        )

    def _update_timeline(self, lang: str) -> None:
        self._content.remove(self._timeline_group)
        self._timeline_group = Adw.PreferencesGroup()
        self._timeline_group.set_title(_("Progress Timeline"))

        history = SubmissionLog.get().get_stats_history(lang)
        if not history:
            self._timeline_group.set_description(_("Not enough data for timeline yet"))
        else:
            # Simple ASCII progress chart
            lines = []
            for snap in history[-10:]:
                pct = snap.get("percentage", 0)
                bar_len = int(pct / 5)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                date = snap["timestamp"][:10]
                lines.append(f"{date}  {bar}  {pct:.1f}%")

            chart_label = Gtk.Label(
                label="\n".join(lines),
                xalign=0,
            )
            chart_label.add_css_class("monospace")
            chart_label.add_css_class("caption")
            chart_label.set_margin_start(12)
            chart_label.set_margin_end(12)
            chart_label.set_margin_top(8)
            chart_label.set_margin_bottom(8)
            chart_label.set_selectable(True)
            self._timeline_group.add(chart_label)

        self._content.append(self._timeline_group)

    def _on_refresh(self, btn: Gtk.Button) -> None:
        self.load_data()

    def _on_export_csv(self, btn: Gtk.Button) -> None:
        csv_data = SubmissionLog.get().export_csv()

        dialog = Gtk.FileDialog()
        dialog.set_initial_name("translation-submissions.csv")
        dialog.save(self._window, None, lambda d, r: self._save_csv(d, r, csv_data))

    def _save_csv(self, dialog, result, csv_data: str) -> None:
        try:
            gfile = dialog.save_finish(result)
            path = gfile.get_path()
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(csv_data)
                self._window.show_toast(_("Exported to %s") % path)
        except GLib.Error:
            pass
