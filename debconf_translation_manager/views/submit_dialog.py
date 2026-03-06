"""Submit Dialog — preview and send translation email."""

from __future__ import annotations

import gettext
from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from debconf_translation_manager.services.l10n_debian import L10nPackageStatus
from debconf_translation_manager.services.settings import Settings
from debconf_translation_manager.services.smtp_sender import send_translation_email
from debconf_translation_manager.services.submission_log import SubmissionLog

if TYPE_CHECKING:
    from debconf_translation_manager.window import MainWindow

_ = gettext.gettext


class SubmitDialog(Adw.Dialog):
    """Email submission preview dialog."""

    def __init__(
        self, window: MainWindow, po_path: str, pkg: L10nPackageStatus
    ) -> None:
        super().__init__()
        self._window = window
        self._po_path = po_path
        self._pkg = pkg

        settings = Settings.get()
        lang = settings.language_code
        lang_name = settings["language_name"]
        cc = settings["default_cc"]

        self.set_title(_("Submit Translation"))
        self.set_content_width(600)
        self.set_content_height(550)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()

        send_btn = Gtk.Button(label=_("Send"))
        send_btn.add_css_class("suggested-action")
        send_btn.connect("clicked", self._on_send)
        header.pack_end(send_btn)
        toolbar.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()
        clamp = Adw.Clamp()
        clamp.set_maximum_size(560)
        clamp.set_margin_top(12)
        clamp.set_margin_bottom(12)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        # Email fields
        email_group = Adw.PreferencesGroup()
        email_group.set_title(_("Email"))

        self._to_row = Adw.EntryRow()
        self._to_row.set_title(_("To"))
        self._to_row.set_text(cc)
        email_group.add(self._to_row)

        self._cc_row = Adw.EntryRow()
        self._cc_row.set_title(_("CC"))
        self._cc_row.set_text(cc)
        email_group.add(self._cc_row)

        self._subject_row = Adw.EntryRow()
        self._subject_row.set_title(_("Subject"))
        self._subject_row.set_text(
            f"[INTL:{lang}] {lang_name} translation for debconf templates of {pkg.package}"
        )
        email_group.add(self._subject_row)

        content.append(email_group)

        # Body
        body_group = Adw.PreferencesGroup()
        body_group.set_title(_("Message Body"))

        body_scroll = Gtk.ScrolledWindow()
        body_scroll.set_min_content_height(150)

        self._body_view = Gtk.TextView()
        self._body_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._body_view.set_left_margin(8)
        self._body_view.set_right_margin(8)
        self._body_view.set_top_margin(4)
        self._body_view.set_bottom_margin(4)

        translator_name = settings["translator_name"]
        default_body = (
            f"Hi,\n\n"
            f"Please find attached the {lang_name} translation for the debconf "
            f"templates of {pkg.package}.\n\n"
            f"Thanks,\n"
            f"{translator_name}\n"
        )
        self._body_view.get_buffer().set_text(default_body)
        body_scroll.set_child(self._body_view)

        frame = Gtk.Frame()
        frame.set_child(body_scroll)
        body_group.add(frame)
        content.append(body_group)

        # Attachment info
        attach_group = Adw.PreferencesGroup()
        attach_group.set_title(_("Attachment"))

        attach_row = Adw.ActionRow()
        attach_row.set_title(Path(po_path).name)
        attach_row.set_subtitle(po_path)
        attach_row.set_icon_name("mail-attachment-symbolic")
        attach_group.add(attach_row)

        content.append(attach_group)

        clamp.set_child(content)
        scroll.set_child(clamp)
        toolbar.set_content(scroll)
        self.set_child(toolbar)

    def _on_send(self, btn: Gtk.Button) -> None:
        to = self._to_row.get_text().strip()
        cc = self._cc_row.get_text().strip()
        subject = self._subject_row.get_text().strip()

        buf = self._body_view.get_buffer()
        start, end = buf.get_bounds()
        body = buf.get_text(start, end, True)

        if not to:
            self._window.show_toast(_("Recipient is required"))
            return

        success, message = send_translation_email(
            to=to, cc=cc, subject=subject, body=body, po_file_path=self._po_path
        )

        if success:
            # Log submission
            try:
                import polib

                po = polib.pofile(self._po_path)
                translated = len(po.translated_entries())
                fuzzy = len(po.fuzzy_entries())
                untranslated = len(po.untranslated_entries())
            except Exception:
                translated = self._pkg.translated
                fuzzy = self._pkg.fuzzy
                untranslated = self._pkg.untranslated

            SubmissionLog.get().log_submission(
                package=self._pkg.package,
                language=self._pkg.language,
                recipient=to,
                subject=subject,
                po_path=self._po_path,
                translated=translated,
                fuzzy=fuzzy,
                untranslated=untranslated,
            )

            self._window.show_toast(_("Translation submitted successfully!"))
            self.close()
        else:
            self._window.show_toast(_("Send failed: %s") % message)
