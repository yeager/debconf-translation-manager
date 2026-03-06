"""Main Adw.Application for Debconf Translation Manager."""

from __future__ import annotations

import gettext
import locale
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from debconf_translation_manager import APP_ID, APP_NAME, __version__

# i18n setup
_bundled_locale = Path(__file__).parent / "locale"
LOCALE_DIR = str(_bundled_locale) if _bundled_locale.is_dir() else "/usr/share/locale"
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
        self._window = None

    def do_activate(self) -> None:
        if self._window is None:
            from debconf_translation_manager.window import MainWindow
            self._window = MainWindow(application=self)
        self._window.present()

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        icon_dir = Path(__file__).parent / "data" / "icons"
        if icon_dir.is_dir():
            Gtk.IconTheme.get_for_display(
                Gdk.Display.get_default()
            ).add_search_path(str(icon_dir / "hicolor" / "scalable" / "apps"))
        self._setup_actions()

    def _setup_actions(self) -> None:
        actions = [
            ("about", self._on_about),
            ("quit", self._on_quit),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def _on_about(self, action, param) -> None:
        about = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon=APP_ID,
            version=__version__,
            developer_name="Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            issue_url="https://github.com/yeager/debconf-translation-manager/issues",
            website="https://github.com/yeager/debconf-translation-manager",
            developers=["Daniel Nylander https://github.com/yeager/"],
            copyright="© 2024–2026 Daniel Nylander",
            comments=_(
                "Manage translations of Debian debconf templates.\n"
                "Browse, translate, and submit translations in one workflow."
            ),
        )
        about.present(self._window)

    def _on_quit(self, action, param) -> None:
        self.quit()
