"""Settings view — configure translator preferences, SMTP, and defaults."""

from __future__ import annotations

import gettext
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from debconf_translation_manager.services.settings import Settings

_ = gettext.gettext


class SettingsView(Gtk.Box):
    """Preferences form backed by :class:`Settings`."""

    def __init__(self, window: Any = None, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._window = window
        self._settings = Settings.get()
        self._build_ui()
        self._load_from_settings()

    def save(self) -> None:
        """Persist settings to disk (Ctrl+S)."""
        self._save_to_settings()
        self._settings.save()
        if self._window:
            self._window.show_toast(_("Settings saved"))

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        title = Gtk.Label(label=_("Settings"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_margin_start(16)
        title.set_margin_top(12)
        title.set_margin_bottom(4)
        self.append(title)

        subtitle = Gtk.Label(
            label=_("Configure translator preferences, language defaults, and SMTP settings"),
            xalign=0,
        )
        subtitle.add_css_class("dim-label")
        subtitle.set_margin_start(16)
        subtitle.set_margin_bottom(8)
        self.append(subtitle)

        self.append(Gtk.Separator())

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # -- Translator group -----------------------------------------------
        translator_group = Adw.PreferencesGroup()
        translator_group.set_title(_("Translator"))
        translator_group.set_description(_("Your identity for PO file headers and bug reports"))

        self._name_row = Adw.EntryRow()
        self._name_row.set_title(_("Name"))
        translator_group.add(self._name_row)

        self._email_row = Adw.EntryRow()
        self._email_row.set_title(_("Email"))
        translator_group.add(self._email_row)

        content.append(translator_group)

        # -- Language group -------------------------------------------------
        lang_group = Adw.PreferencesGroup()
        lang_group.set_title(_("Language"))
        lang_group.set_description(_("Default language for translations"))

        self._lang_code_row = Adw.EntryRow()
        self._lang_code_row.set_title(_("Language code"))
        lang_group.add(self._lang_code_row)

        self._lang_name_row = Adw.EntryRow()
        self._lang_name_row.set_title(_("Language name"))
        lang_group.add(self._lang_name_row)

        content.append(lang_group)

        # -- BTS defaults ---------------------------------------------------
        bts_group = Adw.PreferencesGroup()
        bts_group.set_title(_("BTS Defaults"))
        bts_group.set_description(_("Default values for Debian bug reports"))

        severity_row = Adw.ComboRow()
        severity_row.set_title(_("Severity"))
        severity_model = Gtk.StringList.new(
            ["wishlist", "minor", "normal", "important"]
        )
        severity_row.set_model(severity_model)
        self._severity_row = severity_row
        bts_group.add(severity_row)

        content.append(bts_group)

        # -- SMTP group -----------------------------------------------------
        smtp_group = Adw.PreferencesGroup()
        smtp_group.set_title(_("SMTP"))
        smtp_group.set_description(_("Mail server settings for sending bug reports"))

        self._smtp_host_row = Adw.EntryRow()
        self._smtp_host_row.set_title(_("SMTP host"))
        smtp_group.add(self._smtp_host_row)

        self._smtp_port_row = Adw.EntryRow()
        self._smtp_port_row.set_title(_("SMTP port"))
        smtp_group.add(self._smtp_port_row)

        self._smtp_user_row = Adw.EntryRow()
        self._smtp_user_row.set_title(_("SMTP username"))
        smtp_group.add(self._smtp_user_row)

        self._smtp_tls_row = Adw.SwitchRow()
        self._smtp_tls_row.set_title(_("Use TLS"))
        smtp_group.add(self._smtp_tls_row)

        content.append(smtp_group)

        # -- Save button ----------------------------------------------------
        save_btn = Gtk.Button(label=_("Save Settings"))
        save_btn.add_css_class("suggested-action")
        save_btn.add_css_class("pill")
        save_btn.set_halign(Gtk.Align.CENTER)
        save_btn.connect("clicked", self._on_save_clicked)
        content.append(save_btn)

        clamp.set_child(content)
        scroll.set_child(clamp)
        self.append(scroll)

    # -- data <-> UI -------------------------------------------------------

    def _load_from_settings(self) -> None:
        s = self._settings
        self._name_row.set_text(s["translator_name"])
        self._email_row.set_text(s["translator_email"])
        self._lang_code_row.set_text(s["language_code"])
        self._lang_name_row.set_text(s["language_name"])
        self._smtp_host_row.set_text(s["smtp_host"])
        self._smtp_port_row.set_text(str(s["smtp_port"]))
        self._smtp_user_row.set_text(s["smtp_user"])
        self._smtp_tls_row.set_active(s["smtp_use_tls"])

        severities = ["wishlist", "minor", "normal", "important"]
        try:
            idx = severities.index(s["bts_severity"])
        except ValueError:
            idx = 0
        self._severity_row.set_selected(idx)

    def _save_to_settings(self) -> None:
        s = self._settings
        s["translator_name"] = self._name_row.get_text()
        s["translator_email"] = self._email_row.get_text()
        s["language_code"] = self._lang_code_row.get_text()
        s["language_name"] = self._lang_name_row.get_text()
        s["smtp_host"] = self._smtp_host_row.get_text()
        s["smtp_user"] = self._smtp_user_row.get_text()
        s["smtp_use_tls"] = self._smtp_tls_row.get_active()

        try:
            s["smtp_port"] = int(self._smtp_port_row.get_text())
        except ValueError:
            s["smtp_port"] = 587

        severities = ["wishlist", "minor", "normal", "important"]
        s["bts_severity"] = severities[self._severity_row.get_selected()]

    # -- callbacks ---------------------------------------------------------

    def _on_save_clicked(self, btn: Gtk.Button) -> None:
        self.save()
