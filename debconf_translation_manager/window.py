"""Main application window with Adw.NavigationView."""

from __future__ import annotations

import gettext

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from debconf_translation_manager.services.l10n_debian import L10nPackageStatus
from debconf_translation_manager.views.package_list_page import PackageListPage

_ = gettext.gettext


class MainWindow(Adw.ApplicationWindow):
    """Main application window using NavigationView for page flow."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            default_width=1000,
            default_height=700,
            **kwargs,
        )

        self._toast_overlay = Adw.ToastOverlay()
        self._nav_view = Adw.NavigationView()
        self._toast_overlay.set_child(self._nav_view)
        self.set_content(self._toast_overlay)

        # Create and push main page
        self._package_list_page = PackageListPage(self)
        self._nav_view.push(self._package_list_page)

        # Start loading data
        self._package_list_page.load_data()

    def get_toast_overlay(self) -> Adw.ToastOverlay:
        return self._toast_overlay

    def show_toast(self, message: str) -> None:
        toast = Adw.Toast.new(message)
        self._toast_overlay.add_toast(toast)

    def show_package_detail(self, pkg: L10nPackageStatus) -> None:
        from debconf_translation_manager.views.package_detail_page import (
            PackageDetailPage,
        )

        page = PackageDetailPage(self, pkg)
        self._nav_view.push(page)

    def show_po_editor(self, po_path: str, pkg: L10nPackageStatus) -> None:
        from debconf_translation_manager.views.po_editor_page import PoEditorPage

        page = PoEditorPage(self, po_path, pkg)
        self._nav_view.push(page)

    def show_submit_dialog(self, po_path: str, pkg: L10nPackageStatus) -> None:
        from debconf_translation_manager.views.submit_dialog import SubmitDialog

        dialog = SubmitDialog(self, po_path, pkg)
        dialog.present(self)

    def show_stats(self) -> None:
        from debconf_translation_manager.views.stats_page import StatsPage

        page = StatsPage(self)
        self._nav_view.push(page)
        page.load_data()

    def show_preferences(self) -> None:
        from debconf_translation_manager.views.preferences import PreferencesWindow

        prefs = PreferencesWindow(self)
        prefs.present()
