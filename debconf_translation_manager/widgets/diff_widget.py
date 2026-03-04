"""Side-by-side diff widget with inline change highlighting."""

from __future__ import annotations

import difflib
import gettext

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk, Pango

_ = gettext.gettext


class DiffWidget(Gtk.Box):
    """Side-by-side diff display with character-level highlighting.

    Shows old text on the left, new text on the right, with changed
    characters highlighted in color.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, **kwargs)
        self._old_view: Gtk.TextView | None = None
        self._new_view: Gtk.TextView | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        # Header row
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        old_label = Gtk.Label(label=_("Old"))
        old_label.add_css_class("heading")
        old_label.set_hexpand(True)
        new_label = Gtk.Label(label=_("New"))
        new_label.add_css_class("heading")
        new_label.set_hexpand(True)
        header.append(old_label)
        header.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        header.append(new_label)
        self.append(header)

        # Side-by-side panes
        panes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        panes.set_vexpand(True)

        self._old_view = self._make_text_view()
        self._new_view = self._make_text_view()

        old_scroll = Gtk.ScrolledWindow()
        old_scroll.set_child(self._old_view)
        old_scroll.set_hexpand(True)
        old_scroll.set_vexpand(True)

        new_scroll = Gtk.ScrolledWindow()
        new_scroll.set_child(self._new_view)
        new_scroll.set_hexpand(True)
        new_scroll.set_vexpand(True)

        panes.append(old_scroll)
        panes.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        panes.append(new_scroll)

        frame = Gtk.Frame()
        frame.set_child(panes)
        self.append(frame)

    def _make_text_view(self) -> Gtk.TextView:
        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_left_margin(8)
        tv.set_right_margin(8)
        tv.set_top_margin(8)
        tv.set_bottom_margin(8)
        tv.add_css_class("monospace")

        buf = tv.get_buffer()
        # Create tags for highlighting
        buf.create_tag("removed", background="rgba(255,80,80,0.3)", strikethrough=True)
        buf.create_tag("added", background="rgba(80,200,80,0.3)")
        buf.create_tag("unchanged", foreground="rgba(128,128,128,0.8)")
        return tv

    def set_diff(self, old_text: str, new_text: str) -> None:
        """Set the old and new text and compute the diff highlighting."""
        if self._old_view is None or self._new_view is None:
            return

        old_buf = self._old_view.get_buffer()
        new_buf = self._new_view.get_buffer()
        old_buf.set_text("")
        new_buf.set_text("")

        if not old_text and not new_text:
            return

        # Use SequenceMatcher for character-level diff
        matcher = difflib.SequenceMatcher(None, old_text, new_text)

        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                _insert_tagged(old_buf, old_text[i1:i2], "unchanged")
                _insert_tagged(new_buf, new_text[j1:j2], "unchanged")
            elif op == "replace":
                _insert_tagged(old_buf, old_text[i1:i2], "removed")
                _insert_tagged(new_buf, new_text[j1:j2], "added")
            elif op == "delete":
                _insert_tagged(old_buf, old_text[i1:i2], "removed")
            elif op == "insert":
                _insert_tagged(new_buf, new_text[j1:j2], "added")

    def clear(self) -> None:
        if self._old_view:
            self._old_view.get_buffer().set_text("")
        if self._new_view:
            self._new_view.get_buffer().set_text("")


def _insert_tagged(buf: Gtk.TextBuffer, text: str, tag_name: str) -> None:
    """Insert text at end of buffer with the given tag."""
    end = buf.get_end_iter()
    buf.insert_with_tags_by_name(end, text, tag_name)
