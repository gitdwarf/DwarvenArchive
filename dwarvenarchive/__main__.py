"""DwarvenArchive entry point."""

import os
import sys

# Suppress portal warnings
os.environ.setdefault('GTK_USE_PORTAL', '0')

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib

# Suppress GTK warnings about transient parents (dialogs shown during ops)
def _log_handler(domain, level, message, user_data):
    if 'transient' not in message.lower():
        import sys
        print(f'{domain}: {message}', file=sys.stderr)

GLib.log_set_handler(
    'Gtk',
    GLib.LogLevelFlags.LEVEL_WARNING | GLib.LogLevelFlags.LEVEL_MESSAGE,
    _log_handler, None)

APP_DIR = os.path.dirname(os.path.abspath(__file__))

from .app import DwarvenArchiveApp, setup_i18n
import builtins

_ = setup_i18n(APP_DIR)
builtins._ = _


def main():
    app = DwarvenArchiveApp(APP_DIR)
    sys.exit(app.run(sys.argv))


if __name__ == '__main__':
    main()
