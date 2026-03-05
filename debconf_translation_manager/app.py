"""Main Adw.Application for Debconf Translation Manager."""

from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from debconf_translation_manager import APP_ID, APP_NAME, __version__

# i18n setup
LOCALE_DIR = Path(__file__).parent / "locale"
try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass

gettext.bindtextdomain("debconf-translation-manager", str(LOCALE_DIR))
gettext.textdomain("debconf-translation-manager")
_ = gettext.gettext


class DebconfTranslationManagerApp(Adw.Application):
    """The main application class."""

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._window: MainWindow | None = None

    def do_activate(self) -> None:
        if self._window is None:
            from debconf_translation_manager.window import MainWindow

            self._window = MainWindow(application=self)

        self._window.present()

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        self._setup_actions()
        self._setup_shortcuts()
        self._show_welcome()

    # -- actions --------------------------------------------------------

    def _setup_actions(self) -> None:
        actions = [
            ("about", self._on_about),
            ("quit", self._on_quit),
            ("shortcuts", self._on_shortcuts),
            ("toggle-theme", self._on_toggle_theme),
            ("copy-debug", self._on_copy_debug),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def _setup_shortcuts(self) -> None:
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.shortcuts", ["<Control>question"])
        self.set_accels_for_action("app.toggle-theme", ["<Control>t"])
        self.set_accels_for_action("app.copy-debug", ["<Control><Shift>d"])
        # View shortcuts are set up in the window
        self.set_accels_for_action("win.search", ["<Control>f"])
        self.set_accels_for_action("win.save", ["<Control>s"])
        self.set_accels_for_action("win.export-csv", ["<Control><Shift>e"])
        self.set_accels_for_action("win.export-json", ["<Control><Shift>j"])

    # -- callbacks ------------------------------------------------------

    def _on_about(self, action: Gio.SimpleAction, param_args: None) -> None:
        about = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon="preferences-desktop-locale",
            version=__version__,
            developer_name="Danne L10n Suite",
            license_type=Gtk.License.GPL_3_0,
            issue_url="https://github.com/yeager/debconf-translation-manager/issues",
            website="https://github.com/yeager/debconf-translation-manager",
            developers=["Danne L10n Suite https://github.com/yeager/"],
            copyright="© 2024–2026 Danne L10n Suite",
            comments=_(
                "Manage translations of Debian debconf templates.\n"
                "Part of the Danne L10n Suite."
            ),
        )
        about.add_link(_("Translate on Transifex"), "https://app.transifex.com/danielnylander/debconf-translator/")
        about.present(self._window)

    def _on_quit(self, action: Gio.SimpleAction, param_args: None) -> None:
        self.quit()

    def _on_shortcuts(self, action: Gio.SimpleAction, param_args: None) -> None:
        if self._window is None:
            return
        builder = Gtk.Builder()
        builder.add_from_string(_SHORTCUTS_UI)
        dialog = builder.get_object("shortcuts-window")
        dialog.set_transient_for(self._window)
        dialog.present()

    def _on_toggle_theme(self, action: Gio.SimpleAction, param_args: None) -> None:
        mgr = self.get_style_manager()
        scheme = mgr.get_color_scheme()
        if scheme == Adw.ColorScheme.FORCE_DARK:
            mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif scheme == Adw.ColorScheme.FORCE_LIGHT:
            mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)
        else:
            mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

    def _on_copy_debug(self, action: Gio.SimpleAction, param_args: None) -> None:
        import platform

        lines = [
            f"{APP_NAME} {__version__}",
            f"Python {platform.python_version()}",
            f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}",
            f"Adwaita {Adw.get_major_version()}.{Adw.get_minor_version()}.{Adw.get_micro_version()}",
            f"OS: {platform.system()} {platform.release()}",
        ]
        text = "\n".join(lines)

        if self._window is not None:
            clipboard = self._window.get_clipboard()
            clipboard.set(text)

            toast = Adw.Toast.new(_("Debug info copied to clipboard"))
            self._window.get_toast_overlay().add_toast(toast)

    # -- welcome dialog -------------------------------------------------

    def _show_welcome(self) -> None:
        """Show welcome dialog on first activation."""
        # We defer to first window present via a one-shot idle callback
        GLib.idle_add(self._present_welcome_once)

    def _present_welcome_once(self) -> bool:
        if self._window is None:
            return False  # remove idle

        # Only show once per session
        if getattr(self, "_welcome_shown", False):
            return False
        self._welcome_shown = True

        dialog = Adw.Dialog()
        dialog.set_title(_("Welcome"))
        dialog.set_content_width(480)
        dialog.set_content_height(400)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        icon = Gtk.Image.new_from_icon_name("preferences-desktop-locale")
        icon.set_pixel_size(64)
        box.append(icon)

        title = Gtk.Label(label=APP_NAME)
        title.add_css_class("title-1")
        box.append(title)

        purpose = Gtk.Label(
            label=_(
                "Browse, edit, and review debconf template translations "
                "for Debian packages."
            ),
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        box.append(purpose)

        how = Gtk.Label(
            label=_(
                "Use the sidebar to navigate between the template browser, "
                "translation status dashboard, PO editor, review board, "
                "diff viewer, and statistics."
            ),
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        how.add_css_class("dim-label")
        box.append(how)

        goal = Gtk.Label(
            label=_(
                "Goal: 100% debconf translation coverage for your language!"
            ),
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        goal.add_css_class("accent")
        box.append(goal)

        btn = Gtk.Button(label=_("Get Started"))
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda b: dialog.close())
        box.append(btn)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_title(False)
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(box)
        dialog.set_child(toolbar_view)

        dialog.present(self._window)
        return False  # remove idle


# -- Shortcuts window XML -----------------------------------------------

_SHORTCUTS_UI = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <object class="GtkShortcutsWindow" id="shortcuts-window">
    <property name="modal">1</property>
    <child>
      <object class="GtkShortcutsSection">
        <property name="section-name">shortcuts</property>
        <child>
          <object class="GtkShortcutsGroup">
            <property name="title">General</property>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Search</property>
                <property name="accelerator">&lt;Control&gt;f</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Save</property>
                <property name="accelerator">&lt;Control&gt;s</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Toggle Theme</property>
                <property name="accelerator">&lt;Control&gt;t</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Keyboard Shortcuts</property>
                <property name="accelerator">&lt;Control&gt;question</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Copy Debug Info</property>
                <property name="accelerator">&lt;Control&gt;&lt;Shift&gt;d</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Quit</property>
                <property name="accelerator">&lt;Control&gt;q</property>
              </object>
            </child>
          </object>
        </child>
        <child>
          <object class="GtkShortcutsGroup">
            <property name="title">Export</property>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Export CSV</property>
                <property name="accelerator">&lt;Control&gt;&lt;Shift&gt;e</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Export JSON</property>
                <property name="accelerator">&lt;Control&gt;&lt;Shift&gt;j</property>
              </object>
            </child>
          </object>
        </child>
      </object>
    </child>
  </object>
</interface>
"""
