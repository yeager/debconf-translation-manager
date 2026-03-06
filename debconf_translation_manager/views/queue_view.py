"""Submission Queue View - manage packages ready for submission."""

from __future__ import annotations

import gettext
import subprocess
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk, Pango

from debconf_translation_manager.services.submission_queue import SubmissionQueue, QueueItem
from debconf_translation_manager.services.settings import Settings

if TYPE_CHECKING:
    from debconf_translation_manager.window import MainWindow

_ = gettext.gettext


class QueueView(Gtk.Box):
    """Submission queue management view."""
    
    def __init__(self, window: MainWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window
        self._queue = SubmissionQueue.get()
        self._build_ui()
        self._refresh_list()
    
    def _build_ui(self) -> None:
        # Header
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label=_("Submission Queue")))
        
        # Clear queue button
        clear_btn = Gtk.Button(icon_name="user-trash-symbolic")
        clear_btn.set_tooltip_text(_("Clear queue"))
        clear_btn.connect("clicked", self._on_clear_queue)
        header.pack_start(clear_btn)
        
        self.append(header)
        
        # Info banner
        self._info_banner = Adw.Banner()
        self._info_banner.set_title(_("Ready to submit translations"))
        self._info_banner.set_revealed(False)
        self.append(self._info_banner)
        
        # Empty state / list container
        self._main_stack = Gtk.Stack()
        self._main_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        
        # Empty state
        empty_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        empty_page.set_valign(Gtk.Align.CENTER)
        empty_page.set_margin_start(24)
        empty_page.set_margin_end(24)
        
        empty_icon = Gtk.Image.new_from_icon_name("mail-send-symbolic")
        empty_icon.set_icon_size(Gtk.IconSize.LARGE)
        empty_icon.add_css_class("dim-label")
        empty_page.append(empty_icon)
        
        empty_title = Gtk.Label(label=_("No packages in queue"))
        empty_title.add_css_class("title-2")
        empty_title.add_css_class("dim-label")
        empty_page.append(empty_title)
        
        empty_subtitle = Gtk.Label(label=_("Translate packages and add them to the queue for submission"))
        empty_subtitle.add_css_class("dim-label")
        empty_subtitle.set_wrap(True)
        empty_subtitle.set_justify(Gtk.Justification.CENTER)
        empty_page.append(empty_subtitle)
        
        # List view
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._listbox.add_css_class("boxed-list")
        self._listbox.set_margin_start(12)
        self._listbox.set_margin_end(12)
        self._listbox.set_margin_top(12)
        self._listbox.set_margin_bottom(12)
        
        scroll.set_child(self._listbox)
        
        self._main_stack.add_named(empty_page, "empty")
        self._main_stack.add_named(scroll, "list")
        
        self.append(self._main_stack)
    
    def _refresh_list(self) -> None:
        """Refresh the queue list."""
        # Clear existing items
        while True:
            row = self._listbox.get_first_child()
            if row is None:
                break
            self._listbox.remove(row)
        
        items = self._queue.get_items()
        
        if not items:
            self._main_stack.set_visible_child_name("empty")
            self._info_banner.set_revealed(False)
            return
        
        self._main_stack.set_visible_child_name("list")
        self._info_banner.set_title(
            _("%(count)d packages ready to submit") % {"count": len(items)}
        )
        self._info_banner.set_revealed(True)
        
        # Sort by date added (newest first)
        items.sort(key=lambda x: x.date_added, reverse=True)
        
        for item in items:
            row = self._create_queue_row(item)
            self._listbox.append(row)
    
    def _create_queue_row(self, item: QueueItem) -> Gtk.ListBoxRow:
        """Create a row widget for a queue item."""
        row = Gtk.ListBoxRow()
        row.set_activatable(False)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        
        # Package info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)
        
        # Package name
        name_label = Gtk.Label(label=item.package, xalign=0)
        name_label.add_css_class("heading")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        info_box.append(name_label)
        
        # Stats
        stats_text = _("%(translated)d/%(total)d translated (%(pct)d%%)") % {
            "translated": item.translated,
            "total": item.total,
            "pct": item.percentage
        }
        if item.fuzzy > 0:
            stats_text += _(", %(fuzzy)d fuzzy") % {"fuzzy": item.fuzzy}
        
        stats_label = Gtk.Label(label=stats_text, xalign=0)
        stats_label.add_css_class("dim-label")
        stats_label.add_css_class("caption")
        info_box.append(stats_label)
        
        # Date added
        try:
            from datetime import datetime
            date_added = datetime.fromisoformat(item.date_added.replace('Z', '+00:00'))
            date_str = date_added.strftime(_("%Y-%m-%d %H:%M"))
        except Exception:
            date_str = item.date_added
        
        date_label = Gtk.Label(label=_("Added: %(date)s") % {"date": date_str}, xalign=0)
        date_label.add_css_class("dim-label")
        date_label.add_css_class("caption")
        info_box.append(date_label)
        
        main_box.append(info_box)
        
        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        # Submit button
        submit_btn = Gtk.Button(label=_("Submit"))
        submit_btn.add_css_class("suggested-action")
        submit_btn.connect("clicked", self._on_submit_package, item)
        button_box.append(submit_btn)
        
        # Remove button
        remove_btn = Gtk.Button(icon_name="list-remove-symbolic")
        remove_btn.set_tooltip_text(_("Remove from queue"))
        remove_btn.connect("clicked", self._on_remove_package, item.package)
        button_box.append(remove_btn)
        
        main_box.append(button_box)
        row.set_child(main_box)
        
        return row
    
    def _on_submit_package(self, button, item: QueueItem) -> None:
        """Handle package submission."""
        self._show_submit_dialog(item)
    
    def _on_remove_package(self, button, package: str) -> None:
        """Remove package from queue."""
        if self._queue.remove_package(package):
            self._window.show_toast(_("Removed %(package)s from queue") % {"package": package})
            self._refresh_list()
    
    def _on_clear_queue(self, button) -> None:
        """Clear all packages from queue after confirmation."""
        items = self._queue.get_items()
        if not items:
            return
        
        dialog = Adw.MessageDialog.new(self._window)
        dialog.set_heading(_("Clear Queue?"))
        dialog.set_body(
            _("This will remove all %(count)d packages from the submission queue.") % 
            {"count": len(items)}
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("clear", _("Clear Queue"))
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        
        dialog.connect("response", self._on_clear_queue_response)
        dialog.present()
    
    def _on_clear_queue_response(self, dialog, response) -> None:
        """Handle clear queue confirmation response."""
        if response == "clear":
            count = len(self._queue.get_items())
            self._queue.clear_queue()
            self._window.show_toast(_("Cleared %(count)d packages from queue") % {"count": count})
            self._refresh_list()
    
    def _show_submit_dialog(self, item: QueueItem) -> None:
        """Show submission options dialog."""
        dialog = Adw.MessageDialog.new(self._window)
        dialog.set_heading(_("Submit Translation"))
        dialog.set_body(_("Choose how to submit the translation for %(package)s:") % {"package": item.package})
        
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("email", _("Open Email Client"))
        dialog.add_response("copy", _("Copy to Clipboard"))
        dialog.add_response("save", _("Save as .eml File"))
        
        dialog.set_response_appearance("email", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("email")
        
        dialog.connect("response", self._on_submit_dialog_response, item)
        dialog.present()
    
    def _on_submit_dialog_response(self, dialog, response, item: QueueItem) -> None:
        """Handle submission dialog response."""
        if response == "cancel":
            return
        
        try:
            if response == "email":
                self._open_email_client(item)
            elif response == "copy":
                self._copy_email_to_clipboard(item)
            elif response == "save":
                self._save_email_file(item)
        except Exception as exc:
            self._window.show_toast(_("Error: %(error)s") % {"error": str(exc)})
    
    def _generate_email_content(self, item: QueueItem) -> tuple[str, str, str]:
        """Generate email subject, body, and filename for a submission."""
        settings = Settings.get()
        
        subject = f"[INTL:{item.language_code}] {settings['language_name']} translation of debconf templates for {item.package}"
        
        body = f"""Package: {item.package}
Tags: l10n, patch

Please find attached the {settings['language_name']} translation of the debconf 
templates for the {item.package} package.

This translation was created using the Debconf Translation Manager.

Statistics:
- Translated: {item.translated}/{item.total} ({item.percentage}%)"""

        if item.fuzzy > 0:
            body += f"\n- Fuzzy: {item.fuzzy}"
        if item.untranslated > 0:
            body += f"\n- Untranslated: {item.untranslated}"
        
        body += f"""

Translator: {settings['translator_name']} <{settings['translator_email']}>
Language: {settings['language_name']} ({item.language_code})

-- 
Generated by Debconf Translation Manager v{__version__}"""
        
        filename = f"{item.package}.po"
        
        return subject, body, filename
    
    def _open_email_client(self, item: QueueItem) -> None:
        """Open default email client with pre-filled submission."""
        subject, body, _filename = self._generate_email_content(item)
        
        # Create mailto URL
        import urllib.parse
        mailto_url = f"mailto:submit@bugs.debian.org?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
        
        # Open in default email client
        if not webbrowser.open(mailto_url):
            self._window.show_toast(_("Failed to open email client"))
            return
        
        self._window.show_toast(_("Opened email client - don't forget to attach the PO file!"))
        
        # Show attachment reminder
        toast = Adw.Toast.new(_("Attach file: %(path)s") % {"path": item.po_path})
        toast.set_timeout(8)  # Show longer
        self._window._toast_overlay.add_toast(toast)
    
    def _copy_email_to_clipboard(self, item: QueueItem) -> None:
        """Copy email content to clipboard."""
        subject, body, _filename = self._generate_email_content(item)
        
        full_content = f"To: submit@bugs.debian.org\nSubject: {subject}\n\n{body}"
        
        clipboard = self._window.get_clipboard()
        clipboard.set(full_content)
        
        self._window.show_toast(_("Email content copied to clipboard"))
    
    def _save_email_file(self, item: QueueItem) -> None:
        """Save email as .eml file."""
        subject, body, po_filename = self._generate_email_content(item)
        
        # Create email message
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.application import MIMEApplication
        import os
        
        msg = MIMEMultipart()
        msg['To'] = 'submit@bugs.debian.org'
        msg['Subject'] = subject
        msg['From'] = f"{Settings.get()['translator_name']} <{Settings.get()['translator_email']}>"
        
        # Add body
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Attach PO file if it exists
        if os.path.exists(item.po_path):
            with open(item.po_path, 'rb') as f:
                attachment = MIMEApplication(f.read(), Name=po_filename)
            attachment['Content-Disposition'] = f'attachment; filename="{po_filename}"'
            msg.attach(attachment)
        
        # Save dialog
        dialog = Gtk.FileChooserNative.new(
            _("Save Email"), self._window, Gtk.FileChooserAction.SAVE, _("Save"), _("Cancel")
        )
        dialog.set_current_name(f"{item.package}_submission.eml")
        dialog.connect("response", self._on_save_email_response, msg)
        dialog.show()
    
    def _on_save_email_response(self, dialog, response, msg) -> None:
        """Handle save email file dialog response."""
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                try:
                    with open(file.get_path(), 'w', encoding='utf-8') as f:
                        f.write(msg.as_string())
                    self._window.show_toast(_("Email saved as %(filename)s") % {"filename": file.get_basename()})
                except Exception as exc:
                    self._window.show_toast(_("Failed to save: %(error)s") % {"error": str(exc)})
    
    def refresh(self) -> None:
        """Public method to refresh the queue view."""
        self._refresh_list()


# Import version for email footer
try:
    from debconf_translation_manager import __version__
except ImportError:
    __version__ = "0.8.0"