"""Preferences Window — Adw.PreferencesWindow for app settings."""

from __future__ import annotations

import gettext

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from debconf_translation_manager.services.settings import Settings

_ = gettext.gettext

# Languages with active debconf translations (from ranking page)
DEBCONF_LANGUAGES: list[tuple[str, str]] = [
    ("nl", "Dutch"),
    ("de", "German"),
    ("pt", "Portuguese"),
    ("fr", "French"),
    ("pt_BR", "Brazilian Portuguese"),
    ("es", "Spanish"),
    ("ru", "Russian"),
    ("sv", "Swedish"),
    ("da", "Danish"),
    ("it", "Italian"),
    ("cs", "Czech"),
    ("ja", "Japanese"),
    ("ca", "Catalan"),
    ("vi", "Vietnamese"),
    ("gl", "Galician"),
    ("tr", "Turkish"),
    ("pl", "Polish"),
    ("eu", "Basque"),
    ("ro", "Romanian"),
    ("fi", "Finnish"),
    ("sk", "Slovak"),
    ("ko", "Korean"),
    ("id", "Indonesian"),
    ("zh_CN", "Chinese (China)"),
    ("nb", "Norwegian Bokmål"),
    ("uk", "Ukrainian"),
]


class PreferencesWindow(Adw.PreferencesWindow):
    """Application preferences dialog."""

    def __init__(self, window, **kwargs) -> None:
        super().__init__(**kwargs)
        self._window = window
        self._settings = Settings.get()
        self.set_transient_for(window)
        self.set_modal(True)
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        # --- Language page ---
        lang_page = Adw.PreferencesPage()
        lang_page.set_title(_("Language"))
        lang_page.set_icon_name("preferences-desktop-locale-symbolic")

        lang_group = Adw.PreferencesGroup()
        lang_group.set_title(_("Translation Language"))
        lang_group.set_description(_("Select the language you are translating to"))

        self._lang_combo = Adw.ComboRow()
        self._lang_combo.set_title(_("Language"))
        lang_model = Gtk.StringList.new(
            [f"{code} — {name}" for code, name in DEBCONF_LANGUAGES]
        )
        self._lang_combo.set_model(lang_model)
        lang_group.add(self._lang_combo)

        lang_page.add(lang_group)

        # Translator info
        translator_group = Adw.PreferencesGroup()
        translator_group.set_title(_("Translator"))
        translator_group.set_description(_("Your name and email for PO headers"))

        self._name_row = Adw.EntryRow()
        self._name_row.set_title(_("Name"))
        translator_group.add(self._name_row)

        self._email_row = Adw.EntryRow()
        self._email_row.set_title(_("Email"))
        translator_group.add(self._email_row)

        lang_page.add(translator_group)
        self.add(lang_page)

        # --- Email/SMTP page ---
        smtp_page = Adw.PreferencesPage()
        smtp_page.set_title(_("Email"))
        smtp_page.set_icon_name("mail-send-symbolic")

        # From/CC
        email_group = Adw.PreferencesGroup()
        email_group.set_title(_("Email Settings"))

        self._from_row = Adw.EntryRow()
        self._from_row.set_title(_("From address"))
        email_group.add(self._from_row)

        self._cc_row = Adw.EntryRow()
        self._cc_row.set_title(_("Default CC"))
        email_group.add(self._cc_row)

        smtp_page.add(email_group)

        # SMTP
        smtp_group = Adw.PreferencesGroup()
        smtp_group.set_title(_("SMTP Server"))

        self._smtp_host_row = Adw.EntryRow()
        self._smtp_host_row.set_title(_("Server"))
        smtp_group.add(self._smtp_host_row)

        self._smtp_port_row = Adw.EntryRow()
        self._smtp_port_row.set_title(_("Port"))
        smtp_group.add(self._smtp_port_row)

        self._smtp_user_row = Adw.EntryRow()
        self._smtp_user_row.set_title(_("Username"))
        smtp_group.add(self._smtp_user_row)

        self._smtp_pass_row = Adw.PasswordEntryRow()
        self._smtp_pass_row.set_title(_("Password"))
        smtp_group.add(self._smtp_pass_row)

        self._smtp_tls_row = Adw.SwitchRow()
        self._smtp_tls_row.set_title(_("Use TLS"))
        smtp_group.add(self._smtp_tls_row)

        # Gmail preset
        gmail_btn = Gtk.Button()
        btn_content = Adw.ButtonContent(
            icon_name="mail-send-symbolic",
            label=_("Use Gmail SMTP Preset"),
        )
        gmail_btn.set_child(btn_content)
        gmail_btn.add_css_class("flat")
        gmail_btn.connect("clicked", self._on_gmail_preset)
        smtp_group.add(gmail_btn)

        smtp_page.add(smtp_group)
        self.add(smtp_page)

        # --- Storage page ---
        storage_page = Adw.PreferencesPage()
        storage_page.set_title(_("Storage"))
        storage_page.set_icon_name("drive-harddisk-symbolic")

        cache_group = Adw.PreferencesGroup()
        cache_group.set_title(_("Cache"))

        self._cache_row = Adw.EntryRow()
        self._cache_row.set_title(_("Cache directory"))
        cache_group.add(self._cache_row)

        storage_page.add(cache_group)
        self.add(storage_page)

        # Connect close to save
        self.connect("closed", self._on_closed)

    def _load_settings(self) -> None:
        s = self._settings

        # Language
        lang_code = s["language_code"]
        for i, (code, _) in enumerate(DEBCONF_LANGUAGES):
            if code == lang_code:
                self._lang_combo.set_selected(i)
                break

        self._name_row.set_text(s["translator_name"])
        self._email_row.set_text(s["translator_email"])
        self._from_row.set_text(s["email_from"])
        self._cc_row.set_text(s["default_cc"])

        self._smtp_host_row.set_text(s["smtp_host"])
        self._smtp_port_row.set_text(str(s["smtp_port"]))
        self._smtp_user_row.set_text(s["smtp_user"])
        try:
            self._smtp_pass_row.set_text(s["smtp_password"])
        except Exception:
            pass
        self._smtp_tls_row.set_active(s["smtp_use_tls"])
        self._cache_row.set_text(s["cache_dir"])

    def _save_settings(self) -> None:
        s = self._settings

        idx = self._lang_combo.get_selected()
        if 0 <= idx < len(DEBCONF_LANGUAGES):
            s["language_code"] = DEBCONF_LANGUAGES[idx][0]
            s["language_name"] = DEBCONF_LANGUAGES[idx][1]

        s["translator_name"] = self._name_row.get_text()
        s["translator_email"] = self._email_row.get_text()
        s["email_from"] = self._from_row.get_text()
        s["default_cc"] = self._cc_row.get_text()

        s["smtp_host"] = self._smtp_host_row.get_text()
        try:
            s["smtp_port"] = int(self._smtp_port_row.get_text())
        except ValueError:
            s["smtp_port"] = 587
        s["smtp_user"] = self._smtp_user_row.get_text()
        s["smtp_password"] = self._smtp_pass_row.get_text()
        s["smtp_use_tls"] = self._smtp_tls_row.get_active()
        s["cache_dir"] = self._cache_row.get_text()

        s.save()

    def _on_gmail_preset(self, btn: Gtk.Button) -> None:
        self._smtp_host_row.set_text("smtp.gmail.com")
        self._smtp_port_row.set_text("587")
        self._smtp_tls_row.set_active(True)
        email = self._email_row.get_text()
        if email:
            self._smtp_user_row.set_text(email)

    def _on_closed(self, win) -> None:
        self._save_settings()
