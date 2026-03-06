"""Main application window with sidebar navigation (GNOME Settings style)."""

from __future__ import annotations

import gettext

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

_ = gettext.gettext

# Sidebar items: (id, icon, label)
SIDEBAR_ITEMS = [
    ("packages", "package-x-generic-symbolic", _("Packages")),
    ("editor", "document-edit-symbolic", _("Editor")),
    ("statistics", "org.gnome.Usage-symbolic", _("Statistics")),
    ("queue", "mail-send-symbolic", _("Queue")),
    ("settings", "preferences-system-symbolic", _("Settings")),
]


class MainWindow(Adw.ApplicationWindow):
    """Main window with a vertical icon sidebar and content panel."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            default_width=1100,
            default_height=700,
            **kwargs,
        )

        self._toast_overlay = Adw.ToastOverlay()

        # Main horizontal layout: sidebar | content
        self._main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        # ── Sidebar ──
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sidebar.set_size_request(56, -1)
        sidebar.add_css_class("sidebar-nav")
        sidebar.set_margin_top(8)
        sidebar.set_margin_bottom(8)

        self._sidebar_buttons: dict[str, Gtk.ToggleButton] = {}
        group_btn = None
        for item_id, icon, label in SIDEBAR_ITEMS:
            btn = Gtk.ToggleButton()
            btn.set_icon_name(icon)
            btn.set_tooltip_text(label)
            btn.set_size_request(48, 48)
            btn.set_halign(Gtk.Align.CENTER)
            btn.add_css_class("flat")
            btn.add_css_class("circular")
            if group_btn is not None:
                btn.set_group(group_btn)
            else:
                group_btn = btn
            btn.connect("toggled", self._on_sidebar_toggled, item_id)
            sidebar.append(btn)
            self._sidebar_buttons[item_id] = btn

        # Spacer
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar.append(spacer)

        # About button at bottom
        about_btn = Gtk.Button(icon_name="help-about-symbolic")
        about_btn.set_tooltip_text(_("About"))
        about_btn.set_halign(Gtk.Align.CENTER)
        about_btn.add_css_class("flat")
        about_btn.add_css_class("circular")
        about_btn.connect("clicked", lambda b: self.get_application().activate_action("about", None))
        sidebar.append(about_btn)

        # Separator between sidebar and content
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)

        # ── Content stack ──
        self._content_stack = Gtk.Stack()
        self._content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._content_stack.set_transition_duration(200)
        self._content_stack.set_hexpand(True)
        self._content_stack.set_vexpand(True)

        # Create views lazily but add placeholders
        self._views: dict[str, Gtk.Widget | None] = {}
        for item_id, _icon, label in SIDEBAR_ITEMS:
            self._views[item_id] = None

        self._main_box.append(sidebar)
        self._main_box.append(sep)
        self._main_box.append(self._content_stack)

        self._toast_overlay.set_child(self._main_box)
        self.set_content(self._toast_overlay)

        # Apply custom CSS
        self._apply_css()

        # Select packages by default
        self._sidebar_buttons["packages"].set_active(True)

    def _apply_css(self) -> None:
        css = b"""
        .sidebar-nav {
            background-color: @headerbar_bg_color;
        }
        .sidebar-nav button.circular:checked {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
        }
        .chart-area {
            background-color: @card_bg_color;
            border-radius: 12px;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _on_sidebar_toggled(self, btn: Gtk.ToggleButton, item_id: str) -> None:
        if not btn.get_active():
            return
        self._show_view(item_id)

    def _show_view(self, item_id: str) -> None:
        """Lazily create and show the requested view."""
        if self._views.get(item_id) is None:
            self._create_view(item_id)
        self._content_stack.set_visible_child(self._views[item_id])

    def _create_view(self, item_id: str) -> None:
        if item_id == "packages":
            from debconf_translation_manager.views.package_list_view import PackageListView
            view = PackageListView(self)
            view.load_data()
        elif item_id == "editor":
            from debconf_translation_manager.views.po_editor_view import PoEditorView
            view = PoEditorView(self)
        elif item_id == "statistics":
            from debconf_translation_manager.views.stats_view import StatsView
            view = StatsView(self)
            view.load_data()
        elif item_id == "queue":
            from debconf_translation_manager.views.queue_view import QueueView
            view = QueueView(self)
        elif item_id == "settings":
            from debconf_translation_manager.views.settings_view import SettingsView
            view = SettingsView(self)
        else:
            view = Gtk.Label(label=f"Unknown view: {item_id}")

        self._views[item_id] = view
        self._content_stack.add_named(view, item_id)

    # ── Public API ──

    def show_toast(self, message: str) -> None:
        toast = Adw.Toast.new(message)
        self._toast_overlay.add_toast(toast)

    def open_po_in_editor(self, po_path: str, pkg=None) -> None:
        """Switch to editor view and load the given PO file."""
        from debconf_translation_manager.views.po_editor_view import PoEditorView
        if self._views.get("editor") is None:
            self._create_view("editor")
        editor: PoEditorView = self._views["editor"]
        editor.load_file(po_path, pkg)
        self._sidebar_buttons["editor"].set_active(True)

    def switch_to_view(self, item_id: str) -> None:
        """Programmatically switch to a view."""
        if item_id in self._sidebar_buttons:
            self._sidebar_buttons[item_id].set_active(True)
    
    def add_to_queue(self, package: str, po_path: str, translated: int, fuzzy: int, untranslated: int) -> bool:
        """Add a package to the submission queue."""
        from debconf_translation_manager.services.submission_queue import SubmissionQueue
        queue = SubmissionQueue.get()
        
        if queue.add_package(package, po_path, translated, fuzzy, untranslated):
            self.show_toast(_("Added %(package)s to submission queue") % {"package": package})
            # Refresh queue view if it exists
            if self._views.get("queue") is not None:
                self._views["queue"].refresh()
            return True
        else:
            self.show_toast(_("%(package)s is already in the queue") % {"package": package})
            return False
    
    def refresh_queue_view(self) -> None:
        """Refresh the queue view if it's loaded."""
        if self._views.get("queue") is not None:
            self._views["queue"].refresh()
