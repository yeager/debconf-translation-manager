"""Coordination view — l10n.debian.org coordination workflow.

Claim packages (ITT — Intent To Translate), mark done (RFR — Request
For Review), track status through the full l10n lifecycle.
"""

from __future__ import annotations

import gettext
from datetime import datetime
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk

from debconf_translation_manager.services.l10n_debian import (
    L10nPackageStatus,
    fetch_and_parse,
)
from debconf_translation_manager.services.settings import Settings
from debconf_translation_manager.services.submission_queue import SubmissionQueue
from debconf_translation_manager.widgets.filter_bar import FilterBar
from debconf_translation_manager.widgets.status_badge import StatusBadge

_ = gettext.gettext

# l10n coordination status lifecycle
_LIFECYCLE = [
    ("untranslated", _("Unclaimed")),
    ("ITT", _("Intent To Translate")),
    ("translating", _("Translating")),
    ("RFR", _("Request For Review")),
    ("pending-review", _("Under Review")),
    ("LCFC", _("Last Chance For Comments")),
    ("translated", _("Done / Committed")),
]

_LIFECYCLE_ORDER = {s: i for i, (s, _label) in enumerate(_LIFECYCLE)}


class CoordinationView(Gtk.Box):
    """l10n.debian.org coordination workflow.

    Tracks the full lifecycle of a debconf translation:
    unclaimed → ITT → translating → RFR → review → LCFC → done
    """

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._language = "sv"
        self._coordinator = "Swedish l10n Team"
        self._packages = self._build_coordination_data()
        self._filtered = list(self._packages)
        self._build_ui()
        self._apply_filters()

    def focus_search(self) -> None:
        self._filter_bar.focus_search()

    def get_export_data(self) -> list[dict[str, Any]]:
        return [
            {
                "package": p["package"],
                "status": p["coord_status"],
                "translator": p["translator"],
                "date": p["date"],
            }
            for p in self._filtered
        ]

    # -- data -----------------------------------------------------------

    def _build_coordination_data(self) -> list[dict[str, Any]]:
        """Build coordination data from l10n mock data, mapping to lifecycle stages."""
        l10n_data = fetch_and_parse(self._language)
        packages = []

        status_map = {
            "translated": "translated",
            "pending-review": "RFR",
            "fuzzy": "translating",
            "untranslated": "untranslated",
        }

        for pkg in l10n_data:
            coord_status = status_map.get(pkg.status, pkg.status)
            packages.append({
                "package": pkg.package,
                "coord_status": coord_status,
                "translator": pkg.translator,
                "reviewer": pkg.reviewer,
                "date": pkg.date,
                "deadline": pkg.deadline,
                "bug_number": pkg.bug_number,
            })

        return packages

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        # Title
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_row.set_margin_start(16)
        title_row.set_margin_end(16)
        title_row.set_margin_top(12)
        title_row.set_margin_bottom(4)

        title = Gtk.Label(label=_("l10n Coordination"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        title_row.append(title)

        open_web_btn = Gtk.Button(label=_("Open l10n.debian.org"))
        open_web_btn.connect("clicked", self._on_open_web)
        title_row.append(open_web_btn)

        self.append(title_row)

        # Coordinator info
        coord_info = Gtk.Label(
            label=_("Team: %s · Language: %s") % (self._coordinator, self._language),
            xalign=0,
        )
        coord_info.add_css_class("dim-label")
        coord_info.set_margin_start(16)
        coord_info.set_margin_bottom(8)
        self.append(coord_info)

        # Filter
        status_options = ["All"] + [s for s, _l in _LIFECYCLE]
        self._filter_bar = FilterBar(
            search_placeholder=_("Filter packages…"),
            filters=[(_("Stage"), status_options)],
            on_changed=self._apply_filters,
        )
        self.append(self._filter_bar)

        # Lifecycle pipeline visualization
        self._pipeline_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._pipeline_box.set_margin_start(16)
        self._pipeline_box.set_margin_end(16)
        self._pipeline_box.set_margin_top(4)
        self._pipeline_box.set_margin_bottom(4)
        self._pipeline_box.set_homogeneous(True)

        self._pipeline_labels: dict[str, Gtk.Label] = {}
        for status, label in _LIFECYCLE:
            stage_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            stage_box.set_halign(Gtk.Align.CENTER)

            count = Gtk.Label(label="0")
            count.add_css_class("title-3")
            stage_box.append(count)

            name = Gtk.Label(label=label)
            name.add_css_class("caption")
            name.add_css_class("dim-label")
            stage_box.append(name)

            frame = Gtk.Frame()
            frame.set_child(stage_box)
            self._pipeline_box.append(frame)
            self._pipeline_labels[status] = count

        self.append(self._pipeline_box)
        self.append(Gtk.Separator())

        # Paned: list + detail
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(480)

        # Left: package list
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_size_request(300, -1)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(8)
        self._list_box.set_margin_end(4)
        self._list_box.set_margin_top(8)
        self._list_box.set_margin_bottom(8)
        self._list_box.connect("row-selected", self._on_row_selected)
        list_scroll.set_child(self._list_box)
        paned.set_start_child(list_scroll)

        # Right: detail panel
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_box.set_margin_start(8)
        right_box.set_margin_end(16)
        right_box.set_margin_top(12)
        right_box.set_margin_bottom(12)

        self._det_title = Gtk.Label(xalign=0)
        self._det_title.add_css_class("title-3")
        right_box.append(self._det_title)

        # Info grid
        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(16)

        fields = [
            (_("Current Stage:"), "_det_stage"),
            (_("Translator:"), "_det_translator"),
            (_("Reviewer:"), "_det_reviewer"),
            (_("Date:"), "_det_date"),
            (_("Deadline:"), "_det_deadline"),
            (_("Bug:"), "_det_bug"),
        ]
        for i, (label, attr) in enumerate(fields):
            key = Gtk.Label(label=label, xalign=0)
            key.add_css_class("dim-label")
            grid.attach(key, 0, i, 1, 1)
            val = Gtk.Label(xalign=0)
            val.set_selectable(True)
            grid.attach(val, 1, i, 1, 1)
            setattr(self, attr, val)

        right_box.append(grid)

        # Lifecycle progress
        lifecycle_label = Gtk.Label(label=_("Lifecycle:"), xalign=0)
        lifecycle_label.add_css_class("heading")
        right_box.append(lifecycle_label)

        self._lifecycle_bar = Gtk.ProgressBar()
        self._lifecycle_bar.set_show_text(True)
        right_box.append(self._lifecycle_bar)

        # Action buttons
        actions_label = Gtk.Label(label=_("Actions:"), xalign=0)
        actions_label.add_css_class("heading")
        actions_label.set_margin_top(8)
        right_box.append(actions_label)

        btn_grid = Gtk.FlowBox()
        btn_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        btn_grid.set_max_children_per_line(3)
        btn_grid.set_row_spacing(4)
        btn_grid.set_column_spacing(4)

        self._itt_btn = Gtk.Button(label=_("Claim (ITT)"))
        self._itt_btn.set_tooltip_text(_("Intent To Translate — claim this package"))
        self._itt_btn.connect("clicked", self._on_itt)
        btn_grid.insert(self._itt_btn, -1)

        self._rfr_btn = Gtk.Button(label=_("Submit (RFR)"))
        self._rfr_btn.set_tooltip_text(_("Request For Review — mark translation as ready"))
        self._rfr_btn.add_css_class("suggested-action")
        self._rfr_btn.connect("clicked", self._on_rfr)
        btn_grid.insert(self._rfr_btn, -1)

        self._lcfc_btn = Gtk.Button(label=_("LCFC"))
        self._lcfc_btn.set_tooltip_text(_("Last Chance For Comments"))
        self._lcfc_btn.connect("clicked", self._on_lcfc)
        btn_grid.insert(self._lcfc_btn, -1)

        self._done_btn = Gtk.Button(label=_("Mark Done"))
        self._done_btn.add_css_class("success")
        self._done_btn.connect("clicked", self._on_done)
        btn_grid.insert(self._done_btn, -1)

        self._unclaim_btn = Gtk.Button(label=_("Unclaim"))
        self._unclaim_btn.add_css_class("destructive-action")
        self._unclaim_btn.connect("clicked", self._on_unclaim)
        btn_grid.insert(self._unclaim_btn, -1)

        self._queue_btn = Gtk.Button(label=_("Queue for Submission"))
        self._queue_btn.set_tooltip_text(_("Add to submission queue for BTS filing"))
        self._queue_btn.connect("clicked", self._on_queue_for_submission)
        btn_grid.insert(self._queue_btn, -1)

        right_box.append(btn_grid)

        # Placeholder
        self._placeholder = Adw.StatusPage()
        self._placeholder.set_icon_name("mail-send-symbolic")
        self._placeholder.set_title(_("Select a package"))
        self._placeholder.set_description(
            _("Choose a package to view its coordination status and take actions.")
        )
        self._placeholder.set_vexpand(True)

        self._detail_stack = Gtk.Stack()
        self._detail_stack.add_named(self._placeholder, "placeholder")
        self._detail_stack.add_named(right_box, "detail")
        self._detail_stack.set_visible_child_name("placeholder")

        paned.set_end_child(self._detail_stack)
        self.append(paned)

    # -- filters & display ----------------------------------------------

    def _apply_filters(self) -> None:
        query = self._filter_bar.search_text
        stage_filter = self._filter_bar.get_filter_value(_("Stage"))

        self._filtered = []
        for pkg in self._packages:
            if query and query not in pkg["package"].lower():
                continue
            if stage_filter and stage_filter != "All" and pkg["coord_status"] != stage_filter:
                continue
            self._filtered.append(pkg)

        self._update_pipeline()
        self._rebuild_list()

    def _update_pipeline(self) -> None:
        counts: dict[str, int] = {s: 0 for s, _l in _LIFECYCLE}
        for pkg in self._packages:
            status = pkg["coord_status"]
            if status in counts:
                counts[status] += 1
        for status, label in _LIFECYCLE:
            self._pipeline_labels[status].set_label(str(counts.get(status, 0)))

    def _rebuild_list(self) -> None:
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        sorted_pkgs = sorted(
            self._filtered,
            key=lambda p: (_LIFECYCLE_ORDER.get(p["coord_status"], 99), p["package"]),
        )

        for pkg in sorted_pkgs:
            row = self._make_row(pkg)
            self._list_box.append(row)

        self._detail_stack.set_visible_child_name("placeholder")

    def _make_row(self, pkg: dict[str, Any]) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._pkg = pkg

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)

        name = Gtk.Label(label=pkg["package"], xalign=0)
        name.add_css_class("heading")
        left.append(name)

        info_parts = []
        if pkg["translator"]:
            info_parts.append(pkg["translator"])
        if pkg["date"]:
            info_parts.append(pkg["date"])
        if info_parts:
            info = Gtk.Label(label=" · ".join(info_parts), xalign=0)
            info.add_css_class("caption")
            info.add_css_class("dim-label")
            left.append(info)

        box.append(left)

        # Stage label
        stage_label = Gtk.Label(label=pkg["coord_status"])
        stage_label.add_css_class("caption")

        status_class = {
            "untranslated": "error",
            "ITT": "accent",
            "translating": "accent",
            "RFR": "warning",
            "pending-review": "warning",
            "LCFC": "warning",
            "translated": "success",
        }
        stage_label.add_css_class(status_class.get(pkg["coord_status"], "dim-label"))
        box.append(stage_label)

        row.set_child(box)
        return row

    # -- callbacks ------------------------------------------------------

    def _on_row_selected(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            self._detail_stack.set_visible_child_name("placeholder")
            return

        pkg = row._pkg
        self._det_title.set_label(pkg["package"])
        self._det_stage.set_label(pkg["coord_status"])
        self._det_translator.set_label(pkg["translator"] or _("(unclaimed)"))
        self._det_reviewer.set_label(pkg["reviewer"] or _("(none)"))
        self._det_date.set_label(pkg["date"] or _("(unknown)"))
        self._det_deadline.set_label(pkg["deadline"] or _("(none)"))
        self._det_bug.set_label(pkg["bug_number"] or _("(none)"))

        # Update lifecycle progress bar
        order = _LIFECYCLE_ORDER.get(pkg["coord_status"], 0)
        total = len(_LIFECYCLE) - 1
        fraction = order / total if total > 0 else 0
        self._lifecycle_bar.set_fraction(fraction)

        lifecycle_name = dict(_LIFECYCLE).get(pkg["coord_status"], pkg["coord_status"])
        self._lifecycle_bar.set_text(f"{lifecycle_name} ({order + 1}/{total + 1})")

        # Enable/disable buttons based on current stage
        status = pkg["coord_status"]
        self._itt_btn.set_sensitive(status == "untranslated")
        self._rfr_btn.set_sensitive(status in ("ITT", "translating"))
        self._lcfc_btn.set_sensitive(status in ("RFR", "pending-review"))
        self._done_btn.set_sensitive(status in ("LCFC", "RFR", "pending-review"))
        self._unclaim_btn.set_sensitive(status not in ("untranslated", "translated"))
        self._queue_btn.set_sensitive(status in ("LCFC", "RFR", "pending-review", "translated"))

        self._detail_stack.set_visible_child_name("detail")

    def _set_status(self, new_status: str, message: str) -> None:
        row = self._list_box.get_selected_row()
        if row is None:
            return
        pkg = row._pkg
        pkg["coord_status"] = new_status
        pkg["date"] = datetime.now().strftime("%Y-%m-%d")
        self._apply_filters()
        if self._window:
            self._window.show_toast(message)

    def _on_itt(self, btn: Gtk.Button) -> None:
        self._set_status("ITT", _("Package claimed (ITT)"))

    def _on_rfr(self, btn: Gtk.Button) -> None:
        self._set_status("RFR", _("Translation submitted for review (RFR)"))

    def _on_lcfc(self, btn: Gtk.Button) -> None:
        self._set_status("LCFC", _("Last Chance For Comments (LCFC)"))

    def _on_done(self, btn: Gtk.Button) -> None:
        self._set_status("translated", _("Marked as done"))

    def _on_unclaim(self, btn: Gtk.Button) -> None:
        row = self._list_box.get_selected_row()
        if row is not None:
            row._pkg["translator"] = ""
        self._set_status("untranslated", _("Package unclaimed"))

    def _on_queue_for_submission(self, btn: Gtk.Button) -> None:
        """Add the selected package to the submission queue."""
        row = self._list_box.get_selected_row()
        if row is None:
            return
        pkg = row._pkg
        settings = Settings.get()
        queue = SubmissionQueue.get()
        queue.add(
            package=pkg["package"],
            language=settings.language_code,
            language_name=settings.language_name,
            po_file_path="",
        )
        if self._window:
            self._window.show_toast(
                _("Queued %s for submission") % pkg["package"]
            )

    def _on_open_web(self, btn: Gtk.Button) -> None:
        url = f"https://l10n.debian.org/coordination/{self._language}/"
        Gtk.show_uri(self._window, url, 0)
