"""DwarvenArchive application class."""

import os
import sys
import shutil
import gettext

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio

from .window import ArchiveWindow
from . import formats

_ = gettext.gettext

APP_ID    = 'com.dwarven.archive'
ICON_NAME = 'dwarvenarchive'

MIMETYPES = (
    'application/zip;'
    'application/x-tar;'
    'application/x-compressed-tar;'
    'application/x-bzip-compressed-tar;'
    'application/x-xz-compressed-tar;'
    'application/x-7z-compressed;'
    'application/x-rar;'
    'application/x-lha;'
    'application/x-jar;'
    'inode/directory;'
)

DESKTOP_ENTRY = """\
[Desktop Entry]
Type=Application
Name=DwarvenArchive
Comment=Create and extract archives
Exec=dwarvenarchive %f
Icon=dwarvenarchive
MimeType={mimetypes}
Categories=Utility;Archiving;Compression;
Terminal=false
StartupNotify=false
""".format(mimetypes=MIMETYPES)


def setup_i18n(app_dir):
    """Set up gettext translation from Messages/ directory."""
    locale_dir = os.path.join(app_dir, 'Messages')
    try:
        t = gettext.translation('archive', locale_dir, fallback=True)
        t.install()
        return t.gettext
    except Exception:
        return gettext.gettext



def install_icon(app_dir, force=False):
    """Install icon to hicolor/scalable/apps/.

    Tries /usr/share first. Falls back to ~/.local/share if not permitted.
    """
    src = os.path.join(app_dir, '_icon.svg')
    if not os.path.exists(src):
        return

    candidates = [
        '/usr/share/icons/hicolor/scalable/apps',
        os.path.expanduser('~/.local/share/icons/hicolor/scalable/apps'),
    ]

    for dst_dir in candidates:
        dst = os.path.join(dst_dir, f'{ICON_NAME}.svg')
        if not force and os.path.exists(dst):
            return  # already installed here
        try:
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy2(src, dst)
            break  # success
        except PermissionError:
            continue  # try next
        except Exception as e:
            print(f'Warning: could not install icon to {dst_dir}: {e}', file=sys.stderr)
            continue

    # Ask GTK to rescan
    try:
        from gi.repository import Gdk as _Gdk
        theme = Gtk.IconTheme.get_for_display(_Gdk.Display.get_default())
        if theme:
            theme.rescan_if_needed()
    except Exception:
        pass


def install_desktop(app_dir, force=False):
    """Install .desktop file to ~/.local/share/applications/ for this user."""
    dst_dir = os.path.expanduser('~/.local/share/applications')
    dst = os.path.join(dst_dir, 'dwarvenarchive.desktop')

    if force or not os.path.exists(dst):
        try:
            os.makedirs(dst_dir, exist_ok=True)
            with open(dst, 'w') as f:
                f.write(DESKTOP_ENTRY)
            os.system('update-desktop-database ' + dst_dir + ' 2>/dev/null')
        except Exception as e:
            print(f'Warning: could not install desktop file: {e}', file=sys.stderr)


class DwarvenArchiveApp(Gtk.Application):

    def __init__(self, app_dir):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self.app_dir = app_dir
        install_icon(app_dir)
        install_desktop(app_dir)
        self.connect('activate', self._on_activate)
        self.connect('open', self._on_open)

    def _on_open(self, app, files, n_files, hint):
        """Called by GIO when launched with files via desktop integration."""
        for gfile in files:
            path = gfile.get_path()
            if path:
                self._open_path(path)

    def _on_activate(self, app):
        """Called when launched with no files -- check sys.argv for path."""
        args = sys.argv[1:]

        if not args:
            self._show_info_dialog()
            return

        path = args[0]
        if path != '-' and not path.startswith('/'):
            path = os.path.abspath(path)

        if path != '-' and not os.path.exists(path):
            self._show_error_dialog(
                _('Error: File or directory not found:\n\n%s') % path)
            return

        self._open_path(path)

    def _open_path(self, path):
        """Create and present an ArchiveWindow for the given path."""
        win = ArchiveWindow(self)
        data = formats.DirData(path) if os.path.isdir(path) else formats.FileData(path)
        win.set_data(data)
        win.present()

    def _show_info_dialog(self):
        win = Gtk.ApplicationWindow(application=self)
        win.set_title(_('DwarvenArchive'))
        win.set_default_size(450, 150)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hbox.set_margin_top(12); hbox.set_margin_bottom(12)
        hbox.set_margin_start(12); hbox.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name(ICON_NAME)
        icon.set_pixel_size(48)
        hbox.append(icon)

        label = Gtk.Label(label=_(
            'Launch DwarvenArchive with a file or directory to archive it,\n'
            'or with an archive to extract it.'))
        label.set_wrap(True)
        label.set_xalign(0)
        label.set_hexpand(True)
        hbox.append(label)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.append(hbox)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_end(12); btn_box.set_margin_bottom(12)
        ok_btn = Gtk.Button(label=_('OK'))
        ok_btn.connect('clicked', lambda b: win.close())
        btn_box.append(ok_btn)
        vbox.append(btn_box)

        win.set_child(vbox)
        win.present()

    def _show_error_dialog(self, message):
        win = Gtk.ApplicationWindow(application=self)
        win.set_title(_('Error'))
        win.set_default_size(450, 150)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hbox.set_margin_top(12); hbox.set_margin_bottom(12)
        hbox.set_margin_start(12); hbox.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name('dialog-error')
        icon.set_pixel_size(48)
        hbox.append(icon)

        label = Gtk.Label(label=message)
        label.set_wrap(True)
        label.set_xalign(0)
        label.set_hexpand(True)
        hbox.append(label)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.append(hbox)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_end(12); btn_box.set_margin_bottom(12)
        ok_btn = Gtk.Button(label=_('OK'))
        ok_btn.connect('clicked', lambda b: win.close())
        btn_box.append(ok_btn)
        vbox.append(btn_box)

        win.set_child(vbox)
        win.present()
