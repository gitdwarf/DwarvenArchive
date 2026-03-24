"""Main application window for DwarvenArchive."""

import os
import sys
import time
import threading
import gettext

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

from . import formats

_ = gettext.gettext


class UserCancelledError(Exception):
    pass


# ── Dialog helpers ────────────────────────────────────────────────────────────

def _run_modal(dialog):
    """Run a modal Gtk.Window synchronously. Returns when dialog closes."""
    ctx = GLib.MainContext.default()
    while dialog.get_visible():
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)


def _make_dialog(parent, title, width=400, height=150):
    """Create a standard modal dialog window."""
    d = Gtk.Window()
    d.set_title(title)
    d.set_modal(True)
    d.set_transient_for(parent)
    d.set_default_size(width, height)
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    vbox.set_margin_top(12); vbox.set_margin_bottom(12)
    vbox.set_margin_start(12); vbox.set_margin_end(12)
    d.set_child(vbox)
    return d, vbox


def _make_icon_row(icon_name, message, markup=False):
    """Create an hbox with an icon and label."""
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.set_pixel_size(48)
    hbox.append(icon)
    label = Gtk.Label()
    label.set_wrap(True)
    label.set_xalign(0)
    if markup:
        label.set_markup(message)
    else:
        label.set_label(message)
    hbox.append(label)
    return hbox


def _make_button_row(*buttons):
    """Create right-aligned button box. buttons = list of Gtk.Button."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    box.set_halign(Gtk.Align.END)
    for btn in buttons:
        box.append(btn)
    return box


def _add_key_handler(dialog, keyvals, callback):
    """Add ESC/Enter key handler to a dialog."""
    ctrl = Gtk.EventControllerKey()
    def on_key(c, kv, kc, st):
        if kv in keyvals:
            callback()
            return True
        return False
    ctrl.connect('key-pressed', on_key)
    dialog.add_controller(ctrl)


# ── Main window ───────────────────────────────────────────────────────────────

class ArchiveWindow(Gtk.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app)
        self.set_title('DwarvenArchive')
        self.set_default_size(450, 330)

        self.data = None
        self.operation = None
        self.ops = None
        self.save_thread = None
        self.operation_cancelled = False
        self.current_save_path = None
        self.password = None
        self.updating = 0
        self._saving = False

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(self.vbox)

        self.icon_image = Gtk.Image()
        self.icon_image.set_pixel_size(48)
        self.icon_image.set_margin_top(12)
        self.icon_image.set_margin_bottom(6)
        self.vbox.append(self.icon_image)

        self.filename_entry = Gtk.Entry()
        self.filename_entry.set_margin_start(6)
        self.filename_entry.set_margin_end(6)
        self.filename_entry.set_margin_bottom(6)
        self.filename_entry.connect('changed', self._on_name_changed)
        self.filename_entry.connect('activate', self._on_save)
        self.vbox.append(self.filename_entry)

        self.op_combo = Gtk.ComboBoxText()
        self.op_combo.set_margin_start(6)
        self.op_combo.set_margin_end(6)
        self.op_combo.set_margin_bottom(6)
        self.op_combo.connect('changed', self._on_op_changed)
        self.vbox.append(self.op_combo)

        self.password_choice = Gtk.CheckButton(label=_('Password protect'))
        self.password_choice.set_margin_start(6)
        self.password_choice.set_margin_bottom(6)
        self.vbox.append(self.password_choice)

        self.delete_choice = Gtk.CheckButton(label=_('Delete file afterwards?'))
        self.delete_choice.set_margin_start(6)
        self.delete_choice.set_margin_bottom(6)
        self.delete_choice.set_visible(False)
        self.vbox.append(self.delete_choice)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_margin_start(6)
        self.progress_bar.set_margin_end(6)
        self.progress_bar.set_margin_bottom(6)
        self.progress_bar.set_show_text(True)
        self.progress_bar.set_visible(False)
        self.vbox.append(self.progress_bar)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_start(6)
        button_box.set_margin_end(6)
        button_box.set_margin_bottom(6)

        self.cancel_btn = Gtk.Button(label=_('Cancel'))
        self.cancel_btn.connect('clicked', self._on_cancel)
        button_box.append(self.cancel_btn)

        self.save_btn = Gtk.Button(label=_('Save'))
        self.save_btn.add_css_class('suggested-action')
        self.save_btn.connect('clicked', self._on_save)
        button_box.append(self.save_btn)

        self.vbox.append(button_box)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect('key-pressed', self._on_key_pressed)
        self.add_controller(key_ctrl)

        self.connect('realize', lambda w: GLib.idle_add(self._focus_path))

    def do_move_focus(self, direction):
        """Tab order: entry → op_combo → password → save → cancel → entry."""
        from gi.repository import Gtk as _Gtk
        order = [self.filename_entry, self.op_combo,
                 self.password_choice, self.save_btn, self.cancel_btn]
        current = self.get_focus()
        fwd = direction == _Gtk.DirectionType.TAB_FORWARD
        if current in order:
            idx = order.index(current)
            order[(idx + 1 if fwd else idx - 1) % len(order)].grab_focus()
        else:
            self.filename_entry.grab_focus()

    def _focus_path(self):
        """Focus path entry and select the filename part."""
        self.filename_entry.grab_focus()
        name = self.filename_entry.get_text()
        start = name.rfind('/') + 1
        self.filename_entry.select_region(start, -1)
        return False

    # ── Data setup ────────────────────────────────────────────────────────────

    def set_data(self, data):
        assert not self.data
        self.data = data

        ops = [op for op in formats.operations if op.can_handle(data)]
        name = data.default_name
        self.filename_entry.set_text(name)
        start = name.rfind('/') + 1
        self.filename_entry.select_region(start, -1)

        self.ops = []
        for op in ops:
            self.op_combo.append_text(str(op))
            self.ops.append(op)

        try:
            self.op_combo.set_active(self.ops.index(data.default))
        except ValueError:
            print('Warning: %s not in ops list!' % data.default, file=sys.stderr)

        self.filename_entry.connect('changed', self._on_name_changed)

        if isinstance(data, formats.DirData):
            icon_name, fallback = 'application-x-tar', 'folder'
        else:
            if data.default.type == 'inode/directory':
                icon_name, fallback = 'application-x-compressed-tar', 'package-x-generic'
            else:
                icon_name, fallback = 'application-x-tar', 'folder'
            self.password_choice.set_sensitive(False)

        new_icon = self._make_icon(icon_name, fallback)
        parent = self.icon_image.get_parent()
        if parent:
            parent.remove(self.icon_image)
            parent.prepend(new_icon)
        self.icon_image = new_icon

        if isinstance(data, formats.FileData) and data.path != '-':
            self.delete_choice.set_visible(True)

    def _make_icon(self, icon_name, fallback, size=48):
        img = Gtk.Image()
        img.set_pixel_size(size)
        img.set_margin_top(12)
        img.set_margin_bottom(6)
        img.set_from_icon_name(
            icon_name if Gtk.IconTheme.get_for_display(
                self.get_display()).has_icon(icon_name) else fallback)
        return img

    # ── Signal handlers ───────────────────────────────────────────────────────

    def _on_name_changed(self, entry):
        if self.updating or not self.ops:
            return
        self.updating = 1
        name = entry.get_text()
        for i, op in enumerate(self.ops):
            if op and name.endswith('.' + op.extension):
                self.op_combo.set_active(i)
                break
        self.updating = 0

    def _on_op_changed(self, combo):
        op = self._get_selected_op()
        if not op:
            return
        if isinstance(self.data, formats.DirData) and op.supports_password:
            self.password_choice.set_sensitive(True)
        else:
            self.password_choice.set_sensitive(False)
            self.password_choice.set_active(False)
        if self.updating:
            return
        self.updating = 1
        name = self.filename_entry.get_text()
        for op2 in self.ops:
            if op2 and name.endswith('.' + op2.extension):
                name = name[:-len(op2.extension)-1]
                break
        if op.add_extension:
            name += '.' + op.extension
        self.filename_entry.set_text(name)
        start = name.rfind('/') + 1
        self.filename_entry.select_region(start, -1)
        self.updating = 0

    def _on_key_pressed(self, ctrl, keyval, keycode, state):
        from gi.repository import Gdk
        if keyval == Gdk.KEY_Escape:
            self._on_cancel(None)
            return True
        return False

    def _on_cancel(self, button):
        self.operation_cancelled = True
        if formats.current_command:
            formats.current_command.kill()
        self.close()

    def _on_save(self, _):
        """Resolve path, check overwrite, then run save. Re-entrant guard prevents double-fire."""
        if self._saving:
            return
        self._saving = True

        name = self.filename_entry.get_text().strip()
        op = self._get_selected_op()
        if not op or not name:
            self._saving = False
            return

        path = self._resolve_path(name, op)

        if os.path.exists(path):
            confirmed = self._confirm_overwrite(path)
            # Drain queued events before releasing guard
            ctx = GLib.MainContext.default()
            while ctx.pending():
                ctx.iteration(False)
            if not confirmed:
                self._saving = False
                return

        self._run_save(path)
        self._saving = False

    def _resolve_path(self, name, op):
        """Resolve the target path from the filename entry and op type."""
        if op.type == 'inode/directory':
            dest_dir = name if os.path.isdir(name) else os.path.dirname(name)
            if not dest_dir:
                dest_dir = os.getcwd()
            return os.path.join(dest_dir, os.path.basename(name))
        return name

    def _get_selected_op(self):
        idx = self.op_combo.get_active()
        if idx < 0 or not self.ops:
            return None
        return self.ops[idx]

    # ── Save pipeline ─────────────────────────────────────────────────────────

    def _run_save(self, path):
        try:
            self._do_save(path)
        except UserCancelledError:
            pass

    def _do_save(self, path):
        op = self._get_selected_op()

        if self.password_choice.get_active():
            if not self._show_password_dialog():
                raise UserCancelledError()

        if getattr(self.data, 'is_encrypted', False) and not self.password:
            if not self._show_password_dialog(for_extraction=True):
                raise UserCancelledError()

        self.current_save_path = path
        self.operation_cancelled = False
        self.progress_bar.set_visible(True)
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text(_('Starting...'))
        self.save_btn.set_sensitive(False)
        self.cancel_btn.set_sensitive(True)

        source_size = self._estimate_source_size()

        self.save_result = None
        self.save_thread = threading.Thread(
            target=self._thread_save, args=(path, op), daemon=True)
        self.save_thread.start()

        self._wait_for_save(path, source_size)

        self.progress_bar.set_visible(False)
        self.save_btn.set_sensitive(True)

        if self.operation_cancelled:
            self._handle_cancelled(path)
            GLib.idle_add(self._cleanup_dummy, path)
            self.close()
            return

        if self.save_result:
            status, error = self.save_result
            if status == 'password_error':
                self._retry_password(path, op)
            elif status == 'error':
                raise error

        if self.delete_choice.get_active():
            try:
                os.remove(sys.argv[1])
            except Exception as e:
                print(f'Could not delete source file: {e}', file=sys.stderr)

        self.close()

    def _estimate_source_size(self):
        """Estimate source size for progress bar."""
        if isinstance(self.data, formats.DirData):
            try:
                import subprocess
                r = subprocess.run(['du', '-sb', self.data.path],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    return int(r.stdout.split()[0])
            except Exception:
                pass
        return 0

    def _wait_for_save(self, path, source_size):
        """Spin the main loop while the save thread runs, updating progress."""
        ctx = GLib.MainContext.default()
        last_update = 0
        while self.save_thread.is_alive():
            while ctx.pending():
                ctx.iteration(False)
            now = time.time()
            if now - last_update > 0.1:
                last_update = now
                self._update_progress(path, source_size)
            time.sleep(0.01)
            if self.operation_cancelled:
                break

    def _update_progress(self, path, source_size):
        """Update progress bar from current output file size."""
        if os.path.exists(path):
            try:
                cur = os.path.getsize(path)
                if source_size > 0 and cur > 0:
                    frac = min(cur / source_size, 1.0)
                    self.progress_bar.set_fraction(frac)
                    self.progress_bar.set_text(f'{int(frac * 100)}%')
                    return
            except Exception:
                pass
        self.progress_bar.pulse()
        self.progress_bar.set_text(_('Working...'))

    def _retry_password(self, path, op):
        """Retry loop for wrong password on extraction."""
        if os.path.exists(path) and os.path.isdir(path):
            try:
                os.rmdir(path)
            except Exception:
                pass
        while True:
            self._show_error(_('Incorrect password!\n\nPlease try again.'))
            self.password = None
            if not self._show_password_dialog(for_extraction=True):
                return
            self.save_result = None
            self.save_thread = threading.Thread(
                target=self._thread_save, args=(path, op), daemon=True)
            self.save_thread.start()
            ctx = GLib.MainContext.default()
            while self.save_thread.is_alive():
                while ctx.pending():
                    ctx.iteration(False)
                time.sleep(0.01)
            if self.save_result:
                s2, e2 = self.save_result
                if s2 == 'success':
                    break
                elif s2 == 'password_error':
                    if os.path.exists(path) and os.path.isdir(path):
                        try:
                            os.rmdir(path)
                        except Exception:
                            pass
                    continue
                else:
                    raise e2

    def _thread_save(self, path, op):
        try:
            if hasattr(op, 'save_to_file'):
                if op.supports_password and self.password:
                    op.save_to_file(self.data, path, password=self.password)
                else:
                    op.save_to_file(self.data, path)
            else:
                with open(path, 'wb') as stream:
                    if op.supports_password and self.password:
                        op.save_to_stream(self.data, stream, password=self.password)
                    else:
                        op.save_to_stream(self.data, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
            self.save_result = ('success', None)
        except Exception as e:
            import subprocess
            if isinstance(e, subprocess.CalledProcessError) and \
               (self.password or getattr(self.data, 'is_encrypted', False)):
                self.save_result = ('password_error', e)
            else:
                self.save_result = ('error', e)

    # ── Modal dialogs ─────────────────────────────────────────────────────────

    def _confirm_overwrite(self, path):
        """Ask user to confirm overwriting. Returns True to proceed."""
        from gi.repository import Gdk
        result_ok = [False]

        dialog, vbox = _make_dialog(self, _('Overwrite?'))
        vbox.append(_make_icon_row(
            'dialog-warning',
            f'<b>{os.path.basename(path)}</b> already exists.\nOverwrite it?',
            markup=True))

        cancel_btn = Gtk.Button(label=_('Cancel'))
        cancel_btn.connect('clicked', lambda b: dialog.close())
        overwrite_btn = Gtk.Button(label=_('Overwrite'))
        overwrite_btn.add_css_class('destructive-action')
        overwrite_btn.connect('clicked', lambda b: [result_ok.__setitem__(0, True), dialog.close()])
        vbox.append(_make_button_row(cancel_btn, overwrite_btn))

        _add_key_handler(dialog,
            (Gdk.KEY_Escape, Gdk.KEY_Return, Gdk.KEY_KP_Enter),
            dialog.close)

        dialog.present()
        _run_modal(dialog)
        self._focus_path()
        return result_ok[0]

    def _show_password_dialog(self, for_extraction=False):
        """Prompt for password. Returns True if OK."""
        from gi.repository import Gdk
        if for_extraction:
            title, label_text = _('Archive is password protected'), _('Decryption password:')
        else:
            title = _('Archive password encryption')
            label_text = _('Archive password\n(Empty means no password will be set):')

        result_ok = [False]
        dialog, vbox = _make_dialog(self, title, width=380, height=180)

        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        vbox.append(label)

        entry = Gtk.Entry()
        entry.set_visibility(False)
        vbox.append(entry)

        def on_ok():
            self.password = entry.get_text() or None
            result_ok[0] = True
            dialog.close()

        cancel_btn = Gtk.Button(label=_('Cancel'))
        cancel_btn.connect('clicked', lambda b: dialog.close())
        ok_btn = Gtk.Button(label=_('OK'))
        ok_btn.add_css_class('suggested-action')
        ok_btn.connect('clicked', lambda b: on_ok())
        vbox.append(_make_button_row(cancel_btn, ok_btn))

        entry.connect('activate', lambda e: on_ok())
        _add_key_handler(dialog, (Gdk.KEY_Escape,), dialog.close)

        dialog.present()
        _run_modal(dialog)
        return result_ok[0]

    def _show_error(self, message):
        """Show a simple error dialog."""
        from gi.repository import Gdk
        dialog, vbox = _make_dialog(self, _('Error'), width=350, height=140)
        vbox.append(_make_icon_row('dialog-error', message))
        ok_btn = Gtk.Button(label=_('OK'))
        ok_btn.connect('clicked', lambda b: dialog.close())
        vbox.append(_make_button_row(ok_btn))
        _add_key_handler(dialog, (Gdk.KEY_Escape, Gdk.KEY_Return, Gdk.KEY_KP_Enter), dialog.close)
        dialog.present()
        _run_modal(dialog)

    def _handle_cancelled(self, path):
        """Offer to keep or delete partial file after cancellation."""
        from gi.repository import Gdk
        if not os.path.exists(path):
            return

        dialog, vbox = _make_dialog(self, _('Confirm:'))
        vbox.append(_make_icon_row(
            'dialog-warning',
            _("Delete temporary file '%s'?") % os.path.basename(path)))

        keep_btn = Gtk.Button(label=_('Keep'))
        keep_btn.connect('clicked', lambda b: dialog.close())
        delete_btn = Gtk.Button(label=_('Delete'))
        delete_btn.add_css_class('destructive-action')

        def on_delete(b):
            try:
                os.remove(path)
                open(path, 'w').close()  # dummy so SaveBox stat() doesn't fail
            except Exception as e:
                print(f'Could not delete: {e}', file=sys.stderr)
            dialog.close()

        delete_btn.connect('clicked', on_delete)
        vbox.append(_make_button_row(keep_btn, delete_btn))
        _add_key_handler(dialog, (Gdk.KEY_Escape,), dialog.close)
        dialog.present()
        _run_modal(dialog)

    def _cleanup_dummy(self, path):
        try:
            if os.path.exists(path) and os.path.getsize(path) == 0:
                os.remove(path)
        except Exception:
            pass
        return False
