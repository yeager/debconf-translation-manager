"""Settings View — inline settings panel (not a separate window)."""

from __future__ import annotations

import gettext
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from debconf_translation_manager.services.settings import Settings

if TYPE_CHECKING:
    from debconf_translation_manager.window import MainWindow

_ = gettext.gettext

# Languages with active debconf translations
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


class SettingsView(Gtk.Box):
    """Inline settings panel with save button."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window
        self._settings = Settings.get()
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        # Header
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label=_("Settings")))

        save_btn = Gtk.Button(label=_("Save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        self.append(header)

        # Scrollable content
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # ── Language group ──
        lang_group = Adw.PreferencesGroup()
        lang_group.set_title(_("Translation Language"))
        lang_group.set_description(_("Select the target language for translations"))

        self._lang_combo = Adw.ComboRow()
        self._lang_combo.set_title(_("Language"))
        lang_model = Gtk.StringList.new(
            [f"{code} — {name}" for code, name in DEBCONF_LANGUAGES]
        )
        self._lang_combo.set_model(lang_model)
        lang_group.add(self._lang_combo)

        content.append(lang_group)

        # ── Translator info ──
        translator_group = Adw.PreferencesGroup()
        translator_group.set_title(_("Translator"))
        translator_group.set_description(_("Your name and email for PO headers"))

        self._name_row = Adw.EntryRow()
        self._name_row.set_title(_("Name"))
        translator_group.add(self._name_row)

        self._email_row = Adw.EntryRow()
        self._email_row.set_title(_("Email"))
        translator_group.add(self._email_row)

        content.append(translator_group)

        # ── Transifex ──
        tx_group = Adw.PreferencesGroup()
        tx_group.set_title(_("Transifex"))
        tx_group.set_description(_("Transifex project integration settings"))

        self._tx_project_row = Adw.EntryRow()
        self._tx_project_row.set_title(_("Project name"))
        tx_group.add(self._tx_project_row)

        content.append(tx_group)

        # ── Download directory ──
        dir_group = Adw.PreferencesGroup()
        dir_group.set_title(_("Storage"))

        self._cache_row = Adw.EntryRow()
        self._cache_row.set_title(_("Download directory"))
        dir_group.add(self._cache_row)

        content.append(dir_group)

        # ── Email/SMTP ──
        smtp_group = Adw.PreferencesGroup()
        smtp_group.set_title(_("Email / SMTP"))
        smtp_group.set_description(_("SMTP settings for submitting translations"))

        self._from_row = Adw.EntryRow()
        self._from_row.set_title(_("From address"))
        smtp_group.add(self._from_row)

        self._cc_row = Adw.EntryRow()
        self._cc_row.set_title(_("Default CC"))
        smtp_group.add(self._cc_row)

        self._smtp_host_row = Adw.EntryRow()
        self._smtp_host_row.set_title(_("SMTP Server"))
        smtp_group.add(self._smtp_host_row)

        self._smtp_port_row = Adw.EntryRow()
        self._smtp_port_row.set_title(_("SMTP Port"))
        smtp_group.add(self._smtp_port_row)

        self._smtp_user_row = Adw.EntryRow()
        self._smtp_user_row.set_title(_("SMTP Username"))
        smtp_group.add(self._smtp_user_row)

        self._smtp_pass_row = Adw.PasswordEntryRow()
        self._smtp_pass_row.set_title(_("SMTP Password"))
        smtp_group.add(self._smtp_pass_row)

        self._smtp_tls_row = Adw.SwitchRow()
        self._smtp_tls_row.set_title(_("Use TLS"))
        smtp_group.add(self._smtp_tls_row)

        content.append(smtp_group)

        # ── Editor preferences ──
        editor_group = Adw.PreferencesGroup()
        editor_group.set_title(_("Editor Preferences"))

        self._ext_editor_row = Adw.EntryRow()
        self._ext_editor_row.set_title(_("External editor command"))
        self._ext_editor_row.set_text("")
        editor_group.add(self._ext_editor_row)

        self._monospace_row = Adw.SwitchRow()
        self._monospace_row.set_title(_("Use monospace font"))
        self._monospace_row.set_active(True)
        editor_group.add(self._monospace_row)

        content.append(editor_group)

        clamp.set_child(content)
        scroll.set_child(clamp)
        self.append(scroll)

    def _load_settings(self) -> None:
        s = self._settings

        # Language
        lang_code = s["language_code"]
        for i, (code, _) in enumerate(DEBCONF_LANGUAGES):
            if code == lang_code:
                self._lang_combo.set_selected(i)
                break

        self._name_row.set_text(s["translator_name"] or "")
        self._email_row.set_text(s["translator_email"] or "")
        self._tx_project_row.set_text(s["tx_project"] if "tx_project" in s.as_dict() else "")
        self._from_row.set_text(s["email_from"] or "")
        self._cc_row.set_text(s["default_cc"] or "")
        self._smtp_host_row.set_text(s["smtp_host"] or "")
        self._smtp_port_row.set_text(str(s["smtp_port"]))
        self._smtp_user_row.set_text(s["smtp_user"] or "")
        try:
            self._smtp_pass_row.set_text(s["smtp_password"] or "")
        except Exception:
            pass
        self._smtp_tls_row.set_active(s["smtp_use_tls"])
        self._cache_row.set_text(s["cache_dir"] or "")

        # Editor prefs
        ext_editor = s["external_editor"] if "external_editor" in s.as_dict() else ""
        self._ext_editor_row.set_text(ext_editor)
        mono = s["use_monospace"] if "use_monospace" in s.as_dict() else True
        self._monospace_row.set_active(mono)

    def _on_save(self, btn) -> None:
        s = self._settings

        idx = self._lang_combo.get_selected()
        if 0 <= idx < len(DEBCONF_LANGUAGES):
            s["language_code"] = DEBCONF_LANGUAGES[idx][0]
            s["language_name"] = DEBCONF_LANGUAGES[idx][1]

        s["translator_name"] = self._name_row.get_text()
        s["translator_email"] = self._email_row.get_text()
        s["tx_project"] = self._tx_project_row.get_text()
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
        s["external_editor"] = self._ext_editor_row.get_text()
        s["use_monospace"] = self._monospace_row.get_active()

        s.save()
        self._window.show_toast(_("Settings saved"))
