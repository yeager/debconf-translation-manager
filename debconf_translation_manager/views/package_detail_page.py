"""Package Detail Page — shows package info with action buttons."""

from __future__ import annotations

import gettext
import subprocess
import shutil
import threading
import webbrowser
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from debconf_translation_manager.services.l10n_debian import (
    L10nPackageStatus,
    download_po_file,
)
from debconf_translation_manager.services.settings import Settings
from debconf_translation_manager.services.submission_log import SubmissionLog

if TYPE_CHECKING:
    from debconf_translation_manager.window import MainWindow

_ = gettext.gettext


class PackageDetailPage(Adw.NavigationPage):
    """Detail view for a single package with action buttons."""

    def __init__(self, window: MainWindow, pkg: L10nPackageStatus) -> None:
        super().__init__(title=pkg.package)
        self._window = window
        self._pkg = pkg
        self._po_path: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        # Header
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Content
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # Package info group
        info_group = Adw.PreferencesGroup()
        info_group.set_title(self._pkg.package)
        info_group.set_description(_("Translation status for this package"))

        # Stats rows
        score_row = Adw.ActionRow()
        score_row.set_title(_("Translation Score"))
        score_row.set_subtitle(f"{self._pkg.score}%")
        info_group.add(score_row)

        strings_row = Adw.ActionRow()
        strings_row.set_title(_("Total Strings"))
        strings_row.set_subtitle(str(self._pkg.total))
        info_group.add(strings_row)

        translated_row = Adw.ActionRow()
        translated_row.set_title(_("Translated"))
        translated_row.set_subtitle(str(self._pkg.translated))
        info_group.add(translated_row)

        if self._pkg.fuzzy > 0:
            fuzzy_row = Adw.ActionRow()
            fuzzy_row.set_title(_("Fuzzy"))
            fuzzy_row.set_subtitle(str(self._pkg.fuzzy))
            info_group.add(fuzzy_row)

        untranslated_row = Adw.ActionRow()
        untranslated_row.set_title(_("Untranslated"))
        untranslated_row.set_subtitle(str(self._pkg.untranslated))
        info_group.add(untranslated_row)

        if self._pkg.translator:
            translator_row = Adw.ActionRow()
            translator_row.set_title(_("Translator"))
            translator_row.set_subtitle(self._pkg.translator)
            info_group.add(translator_row)

        content.append(info_group)

        # Actions group
        actions_group = Adw.PreferencesGroup()
        actions_group.set_title(_("Actions"))

        # Download PO
        download_row = Adw.ActionRow()
        download_row.set_title(_("Download PO File"))
        download_row.set_subtitle(
            _("Download the translation file from l10n.debian.org")
        )
        download_row.set_activatable(True)
        download_btn = Gtk.Button(icon_name="folder-download-symbolic")
        download_btn.set_valign(Gtk.Align.CENTER)
        download_btn.add_css_class("flat")
        if not self._pkg.po_url:
            download_btn.set_sensitive(False)
        download_btn.connect("clicked", self._on_download)
        download_row.add_suffix(download_btn)
        download_row.connect("activated", lambda r: self._on_download(None))
        actions_group.add(download_row)

        # Translate
        translate_row = Adw.ActionRow()
        translate_row.set_title(_("Translate"))
        translate_row.set_subtitle(_("Open the PO editor to translate strings"))
        translate_row.set_activatable(True)
        translate_btn = Gtk.Button(icon_name="document-edit-symbolic")
        translate_btn.set_valign(Gtk.Align.CENTER)
        translate_btn.add_css_class("flat")
        translate_btn.connect("clicked", self._on_translate)
        translate_row.add_suffix(translate_btn)
        translate_row.connect("activated", lambda r: self._on_translate(None))
        actions_group.add(translate_row)

        # l10n-lint review
        lint_row = Adw.ActionRow()
        lint_row.set_title(_("Review with l10n-lint"))
        lint_row.set_subtitle(_("Run l10n-lint on the PO file (if installed)"))
        lint_row.set_activatable(True)
        lint_btn = Gtk.Button(icon_name="dialog-information-symbolic")
        lint_btn.set_valign(Gtk.Align.CENTER)
        lint_btn.add_css_class("flat")
        lint_btn.connect("clicked", self._on_lint)
        lint_row.add_suffix(lint_btn)
        actions_group.add(lint_row)

        # Submit
        submit_row = Adw.ActionRow()
        submit_row.set_title(_("Submit Translation"))
        submit_row.set_subtitle(_("Send the translation via email"))
        submit_row.set_activatable(True)
        submit_btn = Gtk.Button(icon_name="mail-send-symbolic")
        submit_btn.set_valign(Gtk.Align.CENTER)
        submit_btn.add_css_class("flat")
        submit_btn.connect("clicked", self._on_submit)
        submit_row.add_suffix(submit_btn)
        submit_row.connect("activated", lambda r: self._on_submit(None))
        actions_group.add(submit_row)

        # View on l10n.debian.org
        web_row = Adw.ActionRow()
        web_row.set_title(_("View on l10n.debian.org"))
        web_row.set_subtitle(_("Open the package page in your browser"))
        web_row.set_activatable(True)
        web_btn = Gtk.Button(icon_name="web-browser-symbolic")
        web_btn.set_valign(Gtk.Align.CENTER)
        web_btn.add_css_class("flat")
        web_btn.connect("clicked", self._on_view_web)
        web_row.add_suffix(web_btn)
        web_row.connect("activated", lambda r: self._on_view_web(None))
        actions_group.add(web_row)

        content.append(actions_group)

        # Status label for download progress
        self._status_label = Gtk.Label(xalign=0)
        self._status_label.add_css_class("dim-label")
        self._status_label.set_margin_start(4)
        content.append(self._status_label)

        # History group
        history = SubmissionLog.get().get_package_history(self._pkg.package)
        if history:
            history_group = Adw.PreferencesGroup()
            history_group.set_title(_("Submission History"))

            for record in history[:10]:
                row = Adw.ActionRow()
                row.set_title(record.timestamp[:19])
                row.set_subtitle(
                    _("To: %(recipient)s — %(translated)dt/%(fuzzy)df/%(untranslated)du")
                    % {
                        "recipient": record.recipient,
                        "translated": record.translated,
                        "fuzzy": record.fuzzy,
                        "untranslated": record.untranslated,
                    }
                )
                history_group.add(row)

            content.append(history_group)

        clamp.set_child(content)
        scroll.set_child(clamp)
        toolbar_view.set_content(scroll)
        self.set_child(toolbar_view)

    def _on_download(self, btn) -> None:
        if not self._pkg.po_url:
            self._window.show_toast(_("No PO download URL available for this package"))
            return

        self._status_label.set_label(_("Downloading PO file…"))
        thread = threading.Thread(target=self._do_download, daemon=True)
        thread.start()

    def _do_download(self) -> None:
        cache_dir = str(Settings.get().cache_dir / "po_files")
        path = download_po_file(self._pkg.po_url, cache_dir)
        GLib.idle_add(self._on_download_done, path)

    def _on_download_done(self, path: str | None) -> bool:
        if path:
            self._po_path = path
            self._status_label.set_label(_("Downloaded: %s") % path)
            self._window.show_toast(_("PO file downloaded successfully"))
        else:
            self._status_label.set_label(_("Download failed"))
            self._window.show_toast(_("Failed to download PO file"))
        return False

    def _on_translate(self, btn) -> None:
        if not self._po_path:
            # Try to download first
            if self._pkg.po_url:
                self._status_label.set_label(_("Downloading PO file first…"))
                thread = threading.Thread(
                    target=self._download_and_translate, daemon=True
                )
                thread.start()
            else:
                self._window.show_toast(_("Download a PO file first"))
        else:
            self._window.show_po_editor(self._po_path, self._pkg)

    def _download_and_translate(self) -> None:
        cache_dir = str(Settings.get().cache_dir / "po_files")
        path = download_po_file(self._pkg.po_url, cache_dir)
        GLib.idle_add(self._on_download_then_edit, path)

    def _on_download_then_edit(self, path: str | None) -> bool:
        if path:
            self._po_path = path
            self._status_label.set_label(_("Downloaded: %s") % path)
            self._window.show_po_editor(path, self._pkg)
        else:
            self._status_label.set_label(_("Download failed"))
            self._window.show_toast(_("Failed to download PO file"))
        return False

    def _on_lint(self, btn) -> None:
        if not self._po_path:
            self._window.show_toast(_("Download a PO file first"))
            return

        if not shutil.which("l10n-lint"):
            self._window.show_toast(_("l10n-lint is not installed"))
            return

        try:
            result = subprocess.run(
                ["l10n-lint", self._po_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout or result.stderr or _("No issues found")
            self._show_lint_dialog(output)
        except Exception as exc:
            self._window.show_toast(_("l10n-lint error: %s") % str(exc))

    def _show_lint_dialog(self, output: str) -> None:
        dialog = Adw.Dialog()
        dialog.set_title(_("l10n-lint Results"))
        dialog.set_content_width(600)
        dialog.set_content_height(400)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        text_view.add_css_class("monospace")
        text_view.set_margin_start(12)
        text_view.set_margin_end(12)
        text_view.set_margin_top(8)
        text_view.set_margin_bottom(8)
        text_view.get_buffer().set_text(output)
        scroll.set_child(text_view)

        toolbar.set_content(scroll)
        dialog.set_child(toolbar)
        dialog.present(self._window)

    def _on_submit(self, btn) -> None:
        if not self._po_path:
            self._window.show_toast(_("Download and translate a PO file first"))
            return
        self._window.show_submit_dialog(self._po_path, self._pkg)

    def _on_view_web(self, btn) -> None:
        lang = Settings.get().language_code
        url = f"https://www.debian.org/international/l10n/po-debconf/{lang}"
        webbrowser.open(url)
