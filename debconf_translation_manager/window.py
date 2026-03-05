"""Main application window with sidebar navigation."""

from __future__ import annotations

import csv
import gettext
import io
import json
from datetime import datetime
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

_ = gettext.gettext

# View identifiers
VIEW_TEMPLATES = "templates"
VIEW_STATUS = "status"
VIEW_EDITOR = "editor"
VIEW_REVIEW = "review"
VIEW_DIFF = "diff"
VIEW_STATS = "statistics"
VIEW_BTS = "bts"
VIEW_DDTSS = "ddtss"
VIEW_COORD = "coordination"
VIEW_QUEUE = "queue"
VIEW_SETTINGS = "settings"


class ProgressDialog:
    """Reusable progress dialog shown during long operations.

    Usage::

        progress = window.show_progress(_("Fetching data…"))
        progress.update(0.3, _("Loading packages…"))
        progress.update(1.0, _("Done"))
        progress.close()
    """

    def __init__(self, parent: Adw.ApplicationWindow, title: str, cancellable: bool = True) -> None:
        self._dialog = Adw.Dialog()
        self._dialog.set_title(title)
        self._dialog.set_content_width(400)
        self._dialog.set_content_height(180)
        self._cancelled = False
        self._on_cancel: Any = None

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_title(True)
        toolbar.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_valign(Gtk.Align.CENTER)

        self._message_label = Gtk.Label(label=title)
        self._message_label.add_css_class("heading")
        box.append(self._message_label)

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(True)
        box.append(self._progress_bar)

        self._detail_label = Gtk.Label(label="")
        self._detail_label.add_css_class("caption")
        self._detail_label.add_css_class("dim-label")
        box.append(self._detail_label)

        if cancellable:
            cancel_btn = Gtk.Button(label=_("Cancel"))
            cancel_btn.add_css_class("destructive-action")
            cancel_btn.add_css_class("pill")
            cancel_btn.set_halign(Gtk.Align.CENTER)
            cancel_btn.connect("clicked", self._on_cancel_clicked)
            box.append(cancel_btn)

        toolbar.set_content(box)
        self._dialog.set_child(toolbar)
        self._dialog.present(parent)

    def update(self, fraction: float, text: str = "") -> None:
        """Update progress bar fraction (0.0–1.0) and detail text."""
        self._progress_bar.set_fraction(min(max(fraction, 0.0), 1.0))
        if text:
            self._detail_label.set_label(text)
            self._progress_bar.set_text(text)

    def close(self) -> None:
        """Close the progress dialog."""
        self._dialog.close()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def set_on_cancel(self, callback: Any) -> None:
        self._on_cancel = callback

    def _on_cancel_clicked(self, btn: Gtk.Button) -> None:
        self._cancelled = True
        if self._on_cancel:
            self._on_cancel()
        self._dialog.close()


class MainWindow(Adw.ApplicationWindow):
    """Main window with sidebar navigation and stacked views."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            default_width=1200,
            default_height=800,
            title="Debconf Translation Manager",
            **kwargs,
        )

        # Auto-load settings on startup
        from debconf_translation_manager.services.settings import Settings
        Settings.get()

        self._views: dict[str, Gtk.Widget] = {}
        self._toast_overlay = Adw.ToastOverlay()
        self._status_label = Gtk.Label(label="")
        self._status_label.add_css_class("dim-label")
        self._status_label.set_halign(Gtk.Align.END)
        self._status_label.set_hexpand(True)

        self._build_ui()
        self._setup_actions()
        self._setup_change_notifier()
        self._update_status(_("Ready"))

    # -- public API ----------------------------------------------------

    def get_toast_overlay(self) -> Adw.ToastOverlay:
        return self._toast_overlay

    def show_toast(self, message: str) -> None:
        self._toast_overlay.add_toast(Adw.Toast.new(message))

    def show_progress(self, title: str, cancellable: bool = True) -> ProgressDialog:
        """Show a modal progress dialog. Returns a :class:`ProgressDialog`."""
        return ProgressDialog(self, title, cancellable=cancellable)

    def navigate_to_editor(
        self, package: str | None = None, po_file_path: str | None = None
    ) -> None:
        """Switch to the PO Editor view, optionally loading a .po file."""
        self._switch_to_view(VIEW_EDITOR)
        editor = self._views.get(VIEW_EDITOR)
        if editor is None:
            return
        if package:
            editor.set_package(package)
        if po_file_path:
            editor.load_po_file(po_file_path, package=package)

    def navigate_to_queue(self) -> None:
        """Switch to the Submission Queue view and refresh it."""
        self._switch_to_view(VIEW_QUEUE)
        queue_view = self._views.get(VIEW_QUEUE)
        if queue_view is not None:
            queue_view.refresh()

    def navigate_to_bts(
        self, package: str | None = None, po_file_path: str | None = None
    ) -> None:
        """Switch to the BTS Workflow view with pre-filled info."""
        self._switch_to_view(VIEW_BTS)
        bts = self._views.get(VIEW_BTS)
        if bts is None:
            return
        bts.prefill(package=package, po_file_path=po_file_path)

    def _switch_to_view(self, view_id: str) -> None:
        """Switch the stack and sidebar to the given view."""
        self._stack.set_visible_child_name(view_id)
        # Update sidebar selection to match
        for i in range(100):
            row = self._sidebar_list.get_row_at_index(i)
            if row is None:
                break
            if getattr(row, "_view_id", None) == view_id:
                self._sidebar_list.select_row(row)
                break
        self._update_status(_("Viewing: %s") % view_id)

    # -- UI construction -----------------------------------------------

    def _build_ui(self) -> None:
        # Lazy import views
        from debconf_translation_manager.views.bts_workflow import BTSWorkflowView
        from debconf_translation_manager.views.coordination import CoordinationView
        from debconf_translation_manager.views.ddtss_workflow import DDTSSWorkflowView
        from debconf_translation_manager.views.diff_view import DiffView
        from debconf_translation_manager.views.po_editor import POEditorView
        from debconf_translation_manager.views.review_board import ReviewBoardView
        from debconf_translation_manager.views.submission_queue import (
            SubmissionQueueView,
        )
        from debconf_translation_manager.views.statistics import StatisticsView
        from debconf_translation_manager.views.template_browser import (
            TemplateBrowserView,
        )
        from debconf_translation_manager.views.settings import SettingsView
        from debconf_translation_manager.views.translation_status import (
            TranslationStatusView,
        )

        # Navigation model — each row: (id, icon, title, View class)
        nav_items = [
            (VIEW_TEMPLATES, "view-list-symbolic", _("Packages"), TemplateBrowserView),
            (VIEW_STATUS, "emblem-default-symbolic", _("Status"), TranslationStatusView),
            (VIEW_EDITOR, "document-edit-symbolic", _("PO Editor"), POEditorView),
            (VIEW_REVIEW, "dialog-information-symbolic", _("Review Board"), ReviewBoardView),
            (VIEW_DIFF, "view-dual-symbolic", _("Diff View"), DiffView),
            (VIEW_COORD, "folder-symbolic", _("Coordination"), CoordinationView),
            (VIEW_QUEUE, "mail-send-symbolic", _("Submission Queue"), SubmissionQueueView),
            (VIEW_BTS, "mail-unread-symbolic", _("BTS Bugs"), BTSWorkflowView),
            (VIEW_DDTSS, "network-transmit-symbolic", _("DDTSS"), DDTSSWorkflowView),
            (VIEW_STATS, "utilities-system-monitor-symbolic", _("Statistics"), StatisticsView),
            (VIEW_SETTINGS, "preferences-system-symbolic", _("Settings"), SettingsView),
        ]

        # Stack for content area
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(200)

        for view_id, icon, title, view_cls in nav_items:
            view = view_cls(window=self)
            self._views[view_id] = view
            self._stack.add_titled(view, view_id, title)

        # Sidebar list
        self._sidebar_list = Gtk.ListBox()
        self._sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._sidebar_list.add_css_class("navigation-sidebar")

        for view_id, icon_name, title, _cls in nav_items:
            row = self._make_nav_row(icon_name, title, view_id)
            self._sidebar_list.append(row)

        self._sidebar_list.connect("row-selected", self._on_nav_selected)
        self._sidebar_list.select_row(self._sidebar_list.get_row_at_index(0))

        # Notification indicator
        self._notif_revealer = Gtk.Revealer()
        self._notif_revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_DOWN
        )
        self._notif_bar = self._build_notification_bar()
        self._notif_revealer.set_child(self._notif_bar)

        # Header bar
        header = Adw.HeaderBar()
        theme_btn = Gtk.Button(icon_name="display-brightness-symbolic")
        theme_btn.set_tooltip_text(_("Toggle theme (Ctrl+T)"))
        theme_btn.set_action_name("app.toggle-theme")
        header.pack_start(theme_btn)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_model = Gio.Menu()
        menu_model.append(_("Keyboard Shortcuts"), "app.shortcuts")
        menu_model.append(_("Copy Debug Info"), "app.copy-debug")
        menu_model.append(_("About"), "app.about")
        menu_btn.set_menu_model(menu_model)
        header.pack_end(menu_btn)

        # Sidebar scrolled window
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_child(self._sidebar_list)
        sidebar_scroll.set_size_request(220, -1)

        sidebar_toolbar = Adw.ToolbarView()
        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_title(True)
        sidebar_header.set_title_widget(Gtk.Label(label=_("Navigation")))
        sidebar_toolbar.add_top_bar(sidebar_header)
        sidebar_toolbar.set_content(sidebar_scroll)

        # Content area with toast overlay
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(self._notif_revealer)
        content_box.append(self._stack)
        content_box.set_vexpand(True)
        content_box.set_hexpand(True)

        self._toast_overlay.set_child(content_box)

        content_toolbar = Adw.ToolbarView()
        content_toolbar.add_top_bar(header)
        content_toolbar.set_content(self._toast_overlay)

        # Status bar at bottom
        status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_bar.set_margin_start(8)
        status_bar.set_margin_end(8)
        status_bar.set_margin_top(4)
        status_bar.set_margin_bottom(4)
        status_bar.append(self._status_label)
        content_toolbar.add_bottom_bar(status_bar)

        # Split view
        split = Adw.OverlaySplitView()
        split.set_sidebar(sidebar_toolbar)
        split.set_content(content_toolbar)
        split.set_collapsed(False)
        split.set_min_sidebar_width(200)
        split.set_max_sidebar_width(280)

        self.set_content(split)

    def _make_nav_row(
        self, icon_name: str, title: str, view_id: str
    ) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        box.append(icon)

        label = Gtk.Label(label=title, xalign=0)
        label.set_hexpand(True)
        box.append(label)

        row.set_child(box)
        row._view_id = view_id  # store for lookup
        return row

    def _build_notification_bar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.add_css_class("toolbar")
        bar.set_margin_start(8)
        bar.set_margin_end(8)
        bar.set_margin_top(4)
        bar.set_margin_bottom(4)

        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        bar.append(icon)

        self._notif_label = Gtk.Label(label="")
        self._notif_label.set_hexpand(True)
        self._notif_label.set_xalign(0)
        bar.append(self._notif_label)

        dismiss = Gtk.Button(icon_name="window-close-symbolic")
        dismiss.add_css_class("flat")
        dismiss.connect("clicked", lambda b: self._notif_revealer.set_reveal_child(False))
        bar.append(dismiss)

        return bar

    def show_notification(self, message: str) -> None:
        self._notif_label.set_label(message)
        self._notif_revealer.set_reveal_child(True)

    # -- actions -------------------------------------------------------

    def _setup_actions(self) -> None:
        search_action = Gio.SimpleAction.new("search", None)
        search_action.connect("activate", self._on_search)
        self.add_action(search_action)

        save_action = Gio.SimpleAction.new("save", None)
        save_action.connect("activate", self._on_save)
        self.add_action(save_action)

        csv_action = Gio.SimpleAction.new("export-csv", None)
        csv_action.connect("activate", self._on_export_csv)
        self.add_action(csv_action)

        json_action = Gio.SimpleAction.new("export-json", None)
        json_action.connect("activate", self._on_export_json)
        self.add_action(json_action)

    # -- signal handlers -----------------------------------------------

    def _on_nav_selected(
        self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None
    ) -> None:
        if row is None:
            return
        view_id = row._view_id
        self._stack.set_visible_child_name(view_id)
        self._update_status(_("Viewing: %s") % self._stack.get_visible_child_name())

    def _on_search(self, action: Gio.SimpleAction, param_args: None) -> None:
        visible = self._stack.get_visible_child()
        if hasattr(visible, "focus_search"):
            visible.focus_search()

    def _on_save(self, action: Gio.SimpleAction, param_args: None) -> None:
        visible = self._stack.get_visible_child()
        if hasattr(visible, "save"):
            visible.save()
            self.show_toast(_("Saved"))

    def _on_export_csv(self, action: Gio.SimpleAction, param_args: None) -> None:
        self._export("csv")

    def _on_export_json(self, action: Gio.SimpleAction, param_args: None) -> None:
        self._export("json")

    def _export(self, fmt: str) -> None:
        visible = self._stack.get_visible_child()
        if not hasattr(visible, "get_export_data"):
            self.show_toast(_("Current view does not support export"))
            return

        data = visible.get_export_data()
        if not data:
            self.show_toast(_("No data to export"))
            return

        dialog = Gtk.FileDialog()
        dialog.set_initial_name(f"debconf_export.{fmt}")

        if fmt == "csv":
            dialog.save(self, None, self._on_csv_save_ready, data)
        else:
            dialog.save(self, None, self._on_json_save_ready, data)

    def _on_csv_save_ready(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, data: list
    ) -> None:
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        if not path:
            return

        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

        with open(path, "w", encoding="utf-8") as f:
            f.write(output.getvalue())
        self.show_toast(_("Exported to %s") % path)

    def _on_json_save_ready(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, data: list
    ) -> None:
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.show_toast(_("Exported to %s") % path)

    # -- change notification polling ------------------------------------

    def _setup_change_notifier(self) -> None:
        from debconf_translation_manager.services.notifier import ChangeNotifier

        self._notifier = ChangeNotifier()
        self._notifier.add_listener(self._on_changes_detected)
        # Poll for template changes every 5 minutes
        self._notifier.start_polling(interval_seconds=300)

    def _on_changes_detected(self, changes: list) -> None:
        if not changes:
            return
        packages = {c.package for c in changes}
        self.show_notification(
            _("%d template change(s) in: %s")
            % (len(changes), ", ".join(sorted(packages)))
        )

    # -- status bar ----------------------------------------------------

    def _update_status(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._status_label.set_label(f"{message}  [{ts}]")
