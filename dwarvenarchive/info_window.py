"""InfoWindow -- shown when DwarvenArchive is launched with no arguments."""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, Gdk, GLib
import os
import urllib.parse
import gettext

_ = gettext.gettext

ICON_NAME = 'dwarvenarchive'

_DROP_SETTLE_MS = 125

class InfoWindow(Gtk.ApplicationWindow):

    def __init__(self, app, on_paths):
        super().__init__(application=app)
        self.set_title(_('DwarvenArchive'))
        self.set_default_size(450, 150)
        self._on_paths = on_paths
        self._pending_paths = []
        self._settle_timer = None
        self._build_ui()
        self._add_key_handler()
        self._add_drop_targets()

    def _build_ui(self):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hbox.set_margin_top(12); hbox.set_margin_bottom(12)
        hbox.set_margin_start(12); hbox.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name(ICON_NAME)
        icon.set_pixel_size(48)
        hbox.append(icon)

        self._label = Gtk.Label(label=_(
            'Drop one or more files, folders or archives onto this window,\n'
            'or launch DwarvenArchive with a path as an argument.'))
        self._label.set_wrap(True)
        self._label.set_xalign(0)
        self._label.set_hexpand(True)
        hbox.append(self._label)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.append(hbox)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_end(12); btn_box.set_margin_bottom(12)
        ok_btn = Gtk.Button(label=_('OK'))
        ok_btn.connect('clicked', lambda b: self.close())
        btn_box.append(ok_btn)
        vbox.append(btn_box)

        self.set_child(vbox)

    def _add_key_handler(self):
        ctrl = Gtk.EventControllerKey()
        def _on_key(c, keyval, keycode, state):
            if keyval in (Gdk.KEY_Escape, Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                self.close()
                return True
            return False
        ctrl.connect('key-pressed', _on_key)
        self.add_controller(ctrl)

    def _add_drop_targets(self):
        formats = Gdk.ContentFormats.new(['text/uri-list', 'text/plain'])
        drop_async = Gtk.DropTargetAsync.new(formats, Gdk.DragAction.COPY)
        drop_async.connect('drag-enter', self._on_drag_enter)
        drop_async.connect('drop', self._on_async_drop)
        self.add_controller(drop_async)

    def _on_drag_enter(self, target, drop, x, y):
        fmts = drop.get_formats()
        return Gdk.DragAction.COPY

    def _on_async_drop(self, target, drop, x, y):
        # Read as a stream -- works with GdkX11Drop and all text MIME types.
        drop.read_async(['text/uri-list', 'UTF8_STRING', 'text/plain'],
                        0, None, self._on_stream_ready, drop)
        return True

    def _on_stream_ready(self, source, result, drop):
        try:
            stream, mime_type = drop.read_finish(result)
            stream.read_bytes_async(65536, 0, None, self._on_bytes_ready, (drop, mime_type))
        except Exception as e:
            drop.finish(Gdk.DragAction.COPY)

    def _on_bytes_ready(self, source, result, user_data):
        drop, mime_type = user_data
        try:
            gbytes = source.read_bytes_finish(result)
            raw = gbytes.get_data()
            text = raw.decode('utf-8', errors='replace').strip()
        except Exception as e:
            drop.finish(Gdk.DragAction.COPY)
            return

        drop.finish(Gdk.DragAction.COPY)
        paths = self._parse_drop_text(text)
        for p in paths:
            if p not in self._pending_paths:
                self._pending_paths.append(p)
        if self._pending_paths:
            self._update_label()
            self._reset_timer()

    @staticmethod
    def _parse_drop_text(text):
        """Parse paths from a drop value.

        Handles:
        - Standard text/uri-list: newline-separated file:// URIs
        - ROXFiler: space-separated absolute paths
        - Mixed: lines that are either URIs or raw paths
        """
        paths = []

        # Try newline-separated first (standard text/uri-list)
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith('#')]
        if lines:
            for line in lines:
                if line.startswith('file://'):
                    path = urllib.parse.unquote(urllib.parse.urlparse(line).path)
                    if path and os.path.exists(path):
                        paths.append(path)
                elif line.startswith('/') and os.path.exists(line):
                    paths.append(line)

        if paths:
            return paths

        # Fallback: space-separated absolute paths (ROXFiler GTK2 style)
        for token in text.split():
            token = token.strip()
            if token.startswith('/') and os.path.exists(token):
                paths.append(token)

        return paths

    def _reset_timer(self):
        if self._settle_timer is not None:
            GLib.source_remove(self._settle_timer)
        self._settle_timer = GLib.timeout_add(_DROP_SETTLE_MS, self._on_settle)

    def _on_settle(self):
        self._settle_timer = None
        paths = list(self._pending_paths)
        self._pending_paths.clear()
        if paths:
            self.close()
            self._on_paths(paths)
        return False

    def _update_label(self):
        n = len(self._pending_paths)
        if n == 1:
            name = os.path.basename(self._pending_paths[0])
            self._label.set_label(_('1 item: %s') % name)
        else:
            self._label.set_label(_('%d items ready.') % n)
