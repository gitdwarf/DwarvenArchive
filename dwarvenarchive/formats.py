"""Archive format definitions and operations.

Handles detection, compression, decompression, archiving and extraction
of all supported archive formats via external command-line utilities.
"""

import os
import sys
import subprocess
import threading
import signal
import gettext

_ = gettext.gettext

current_command = None


class PipeThroughCommand:
    """Execute a shell command, optionally piping data through it."""

    def __init__(self, command, src=None, dst=None):
        self.command = command
        self.src = src
        self.dst = dst
        self.process = None
        self.error = None
        self.cancelled = False

        stdin = subprocess.PIPE if src else None
        stdout = subprocess.PIPE if dst else None

        self.process = subprocess.Popen(
            command, shell=True, stdin=stdin, stdout=stdout,
            stderr=subprocess.PIPE, close_fds=True
        )

        if src:
            self.input_thread = threading.Thread(target=self._write_input)
            self.input_thread.daemon = True
            self.input_thread.start()

        if dst:
            self.output_thread = threading.Thread(target=self._read_output)
            self.output_thread.daemon = True
            self.output_thread.start()

    def _write_input(self):
        try:
            chunk_size = 4096
            while True:
                if self.cancelled:
                    break
                data = self.src.read(chunk_size)
                if not data:
                    break
                self.process.stdin.write(data)
            self.process.stdin.close()
        except Exception as e:
            if not self.cancelled:
                self.error = e

    def _read_output(self):
        try:
            chunk_size = 4096
            while True:
                if self.cancelled:
                    break
                data = self.process.stdout.read(chunk_size)
                if not data:
                    break
                self.dst.write(data)
        except Exception as e:
            if not self.cancelled:
                self.error = e

    def wait(self):
        if hasattr(self, 'input_thread'):
            self.input_thread.join()
        if hasattr(self, 'output_thread'):
            self.output_thread.join()

        returncode = self.process.wait()
        stderr_data = self.process.stderr.read()

        if returncode != 0 and stderr_data:
            sys.stderr.write(stderr_data.decode('utf-8', errors='replace'))

        if self.cancelled:
            return -1
        if self.error:
            raise self.error
        if returncode != 0:
            raise subprocess.CalledProcessError(returncode, self.command)
        return returncode

    def kill(self):
        self.cancelled = True
        if self.process and self.process.poll() is None:
            try:
                import time
                os.kill(self.process.pid, signal.SIGTERM)
                time.sleep(0.1)
                if self.process.poll() is None:
                    os.kill(self.process.pid, signal.SIGKILL)
            except Exception:
                pass


def pipe_through_command(command, src, dst):
    global current_command
    assert not current_command
    try:
        if src:
            src.seek(0)
    except Exception:
        pass
    current_command = PipeThroughCommand(command, src, dst)
    try:
        current_command.wait()
    finally:
        current_command = None


def shell_escape(text):
    """Escape text for safe use in shell commands."""
    return "'" + text.replace("'", "'\"'\"'") + "'"


def Tmp(mode='w+b'):
    """Create a seekable, randomly named temp file (deleted automatically after use)."""
    import tempfile
    return tempfile.NamedTemporaryFile(mode, suffix='-archive')


operations = []


class Operation:
    add_extension = False
    supports_password = False

    def __init__(self, extension):
        operations.append(self)
        self.extension = extension

    def can_handle(self, data):
        return isinstance(data, FileData)

    def save_to_stream(self, data, stream):
        pipe_through_command(self.command, data.source, stream)


class Compress(Operation):
    """Compress a stream into another stream."""
    add_extension = True

    def __init__(self, extension, command, type):
        Operation.__init__(self, extension)
        self.command = command
        self.type = type

    def __str__(self):
        return _('Compress as .%s') % self.extension


class Decompress(Operation):
    """Decompress a stream into another stream."""
    type = 'text/plain'

    def __init__(self, extension, command):
        Operation.__init__(self, extension)
        self.command = command

    def __str__(self):
        return _('Decompress .%s') % self.extension


class Extract(Operation):
    """Extract an archive to a directory."""
    type = 'inode/directory'

    def __init__(self, extension, command, supports_password=False):
        """If command has a %s then the source path is inserted, else uses stdin."""
        Operation.__init__(self, extension)
        self.command = command
        self.supports_password = supports_password

    def __str__(self):
        return _('Extract from a .%s') % self.extension

    def save_to_stream(self, data, stream):
        raise Exception(_('This operation creates a directory, so you have '
                'to drag to a filer window on the local machine'))

    def save_to_file(self, data, path, password=None):
        if os.path.exists(path):
            if not os.path.isdir(path):
                raise Exception(_("'%s' already exists and is not a directory!") % path)
        if not os.path.exists(path):
            os.mkdir(path)
        os.chdir(path)
        command = self.command
        source = data.source

        if password and self.supports_password:
            if self.extension in ['zip', 'jar']:
                command = command.replace('unzip ', f'unzip -P {shell_escape(password)} ')
            elif self.extension == '7z':
                command = command.replace('7z x', f'7z x -p{shell_escape(password)}')

        if command.find('%s') != -1:
            command = command % shell_escape(source.name)
            source = None
        try:
            pipe_through_command(command, source, None)
        finally:
            try:
                os.rmdir(path)
            except Exception:
                pass
            if os.path.exists(path):
                self.pull_up(path)

    def pull_up(self, path):
        """If we created only a single subdirectory, move it up."""
        dirs = os.listdir(path)
        if len(dirs) != 1:
            return
        subdir = dirs[0]
        unneeded_path = os.path.join(path, subdir)
        if not os.path.isdir(unneeded_path):
            return
        import random
        tmp_path = os.path.join(path, 'tmp-' + str(random.randint(0, 100000)))
        os.rename(unneeded_path, tmp_path)
        for file in os.listdir(tmp_path):
            os.rename(os.path.join(tmp_path, file), os.path.join(path, file))
        os.rmdir(tmp_path)


class Archive(Operation):
    """Create an archive from a directory."""
    add_extension = True

    def __init__(self, extension, command, type, supports_password=False):
        assert command.find('%s') != -1
        Operation.__init__(self, extension)
        self.command = command
        self.type = type
        self.supports_password = supports_password

    def __str__(self):
        return _('Create .%s archive') % self.extension

    def can_handle(self, data):
        return isinstance(data, DirData)

    def save_to_stream(self, data, stream, password=None):
        os.chdir(os.path.dirname(data.path))
        basename = os.path.basename(data.path)
        command = self.command % shell_escape(basename)

        if password and self.supports_password:
            if self.extension in ('zip', 'jar'):
                command = command.replace('zip ', f'zip -P {shell_escape(password)} ', 1)

        pipe_through_command(command, None, stream)


class FileArchive(Operation):
    """Create an archive that outputs to a file rather than stdout."""
    add_extension = True

    def __init__(self, extension, command, type, supports_password=False):
        assert command.count('%s') == 2
        Operation.__init__(self, extension)
        self.command = command
        self.type = type
        self.supports_password = supports_password

    def __str__(self):
        return _('Create .%s archive') % self.extension

    def can_handle(self, data):
        return isinstance(data, DirData)

    def save_to_stream(self, data, stream, password=None):
        import tempfile
        os.chdir(os.path.dirname(data.path))
        basename = os.path.basename(data.path)

        with tempfile.NamedTemporaryFile(suffix='.' + self.extension, delete=False) as tmp:
            tmp_path = tmp.name
        os.unlink(tmp_path)

        try:
            command = self.command % (shell_escape(tmp_path), shell_escape(basename))

            if password and self.supports_password:
                if self.extension == '7z':
                    command = command.replace('7z a', f'7z a -p{shell_escape(password)}', 1)

            pipe_through_command(command, None, None)

            with open(tmp_path, 'rb') as f:
                chunk_size = 4096
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    stream.write(chunk)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Format definitions
# ---------------------------------------------------------------------------

# Extract operations
zip   = Extract('zip',   'unzip -q %s', supports_password=True)
tgz   = Extract('tgz',   'gunzip -c - | tar xf -')
tbz   = Extract('tar.bz2', 'bunzip2 -c - | tar xf -')
tarz  = Extract('tar.Z', 'uncompress -c - | tar xf -')
tlz   = Extract('tlz',   'unlzma -c - | tar xf -')
txz   = Extract('txz',   'unxz -c - | tar xf -')
rar   = Extract('rar',   'unrar x %s')
ace   = Extract('ace',   'unace x %s')
tar   = Extract('tar',   'tar xf -')
rpm   = Extract('rpm',   'rpm2cpio - | cpio -id --quiet')
cpio  = Extract('cpio',  'cpio -id --quiet')
deb   = Extract('deb',   'ar x %s')
jar   = Extract('jar',   'unzip -q %s', supports_password=True)
lha   = Extract('lha',   'lha x %s')
sevenz = Extract('7z',   '7z x %s >/dev/null 2>&1', supports_password=True)

# Archive operations
make_archive = Archive('zip',     'zip -9qr - %s',          'application/zip',                     supports_password=True)
Archive('tgz',     'tar cf - %s | gzip -9',      'application/x-compressed-tar')
Archive('tar.gz',  'tar cf - %s | gzip -9',      'application/x-compressed-tar')
Archive('tar.bz2', 'tar cf - %s | bzip2 -9',     'application/x-bzip-compressed-tar')
Archive('tlz',     'tar cf - %s | lzma -9',      'application/x-lzma-compressed-tar')
Archive('tar.lzma','tar cf - %s | lzma -9',      'application/x-lzma-compressed-tar')
Archive('txz',     'tar cf - %s | xz -9',        'application/x-xz-compressed-tar')
Archive('tar.xz',  'tar cf - %s | xz -9',        'application/x-xz-compressed-tar')
Archive('jar',     'zip -9qr - %s',              'application/x-jar',                            supports_password=True)
Archive('tar',     'tar cf - %s',                'application/x-tar')
Archive('lha',     'lha c - %s',                 'application/x-lha')

FileArchive('7z',  '7z a -bd -bb0 -mx=9 %s %s >/dev/null 2>&1', 'application/x-7z-compressed',  supports_password=True)

# Compress operations (after archives so .tar.gz matches before .gz)
make_gz = Compress('gz',   'gzip -9 -c -',         'application/x-gzip')
Compress('bz2',  'bzip2 -9 -c -',        'application/x-bzip')
Compress('lzma', 'lzma -9 -c -',         'application/x-lzma')
Compress('xz',   'xz -9 -c -',           'application/x-xz')
Compress('uue',  'uuencode /dev/stdout', 'application/x-uuencoded')

# Decompress operations
gz   = Decompress('gz',   'gunzip -c -')
bz2  = Decompress('bz2',  'bunzip2 -ck -')
uue  = Decompress('uue',  'uudecode -o /dev/stdout')
z    = Decompress('Z',    'uncompress -c -')
lzma = Decompress('lzma', 'unlzma -c -')
xz   = Decompress('xz',   'unxz -c -')

aliases = {
    'tar.gz':  'tgz',
    'tar.bz':  'tar.bz2',
    'tbz':     'tar.bz2',
    'tar.lzma':'tlz',
    'tar.xz':  'txz',
    'bz':      'bz2',
}

known_extensions = {}
for _op in operations:
    try:
        known_extensions[_op.extension] = None
    except AttributeError:
        pass


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

class FileData:
    """A file on the local filesystem."""
    mode = None

    def __init__(self, path):
        self.path = path

        if path == '-':
            source = sys.stdin.buffer
        else:
            try:
                source = open(path, 'rb')
                self.mode = os.stat(path).st_mode
            except Exception as e:
                print(f'Error opening file: {e}', file=sys.stderr)
                sys.exit(1)

        self.path = path
        start = source.read(300)
        try:
            if source is sys.stdin.buffer:
                raise Exception('Always copy stdin!')
            source.seek(0)
            self.source = source
        except Exception:
            import shutil
            tmp = Tmp()
            tmp.write(start)
            tmp.flush()
            shutil.copyfileobj(source, tmp)
            tmp.seek(0)
            tmp.flush()
            self.source = tmp

        self.default = self.guess_format(start)

        try:
            self.is_encrypted = self.check_if_encrypted()
        except Exception:
            self.is_encrypted = False

        if path == '-':
            name = 'Data'
        else:
            name = path
            for ext in known_extensions:
                if path.endswith('.' + ext):
                    new = path[:-len(ext)-1]
                    if len(new) < len(name):
                        name = new
        if self.default.add_extension:
            name += '.' + self.default.extension

        if name == path:
            if '.' in os.path.basename(name):
                name = name[:name.rindex('.')]
            else:
                name += '.unpacked'

        self.default_name = name

    def guess_format(self, data):
        """Return a good default Operation, judging by the first 300 bytes."""
        l = len(data)

        def string(offset, match):
            if isinstance(match, str):
                match = match.encode('latin-1')
            return data[offset:offset + len(match)] == match

        def short(offset, match):
            if l > offset + 1:
                a = data[offset]
                b = data[offset + 1]
                return ((a == match & 0xff) and (b == (match >> 8))) or \
                    (b == match & 0xff) and (a == (match >> 8))
            return 0

        if string(257, 'ustar\0') or string(257, 'ustar\040\040\0'):
            return tar
        if short(0, 0o70707) or short(0, 0o143561) or string(0, '070707') or \
           string(0, '070701') or string(0, '070702'):
            return cpio
        if string(0, '!<arch>') or string(0, '\\<ar>') or string(0, '<ar>'):
            if string(7, '\ndebian'):
                return deb
        if string(0, 'Rar!'):
            return rar
        if string(7, '**ACE**'):
            return ace
        if string(0, 'PK\003\004') or string(0, 'PK00'):
            return zip
        if string(0, '\xed\xab\xee\xdb'):
            return rpm
        if (string(2, '-lz') or string(2, '-lh')) and data[6] == ord('-'):
            return lha
        if string(0, '7z\xbc\xaf\x27\x1c'):
            return sevenz
        if string(0, '\037\213'):
            if self.path.endswith('.tar.gz') or self.path.endswith('.tgz'):
                return tgz
            return gz
        if string(0, 'BZh') or string(0, 'BZ'):
            if self.path.endswith('.tar.bz') or self.path.endswith('.tar.bz2') or \
               self.path.endswith('.tbz') or self.path.endswith('.tbz2'):
                return tbz
            return bz2
        if string(0, ']\0\0') and (0 == data[3] & 0x7f):
            if self.path.endswith('.tar.lzma') or self.path.endswith('.tlz'):
                return tlz
            return lzma
        if string(0, '\xfd7zXZ\0'):
            if self.path.endswith('.tar.xz') or self.path.endswith('.txz'):
                return txz
            return xz
        if string(0, 'begin '):
            return uue
        if string(0, '\037\235'):
            if self.path.endswith('.tar.Z'):
                return tarz
            return z

        return make_gz

    def check_if_encrypted(self):
        """Check if the archive is password protected."""
        if self.path == '-':
            return False

        ext = self.path.lower()
        if not (ext.endswith('.zip') or ext.endswith('.7z') or ext.endswith('.jar')):
            return False

        try:
            result = subprocess.run(
                ['7z', 'l', '-slt', self.path],
                capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                if line.lower().strip().startswith('encrypted =') and '+' in line:
                    return True
        except Exception:
            pass

        try:
            if ext.endswith('.zip') or ext.endswith('.jar'):
                result = subprocess.run(
                    ['unzip', '-Z', '-1', self.path],
                    capture_output=True, text=True, timeout=5)
                if 'encrypted' in result.stdout.lower() or 'encrypted' in result.stderr.lower():
                    return True
        except Exception:
            pass

        return False


class DirData:
    mode = None

    def __init__(self, path):
        self.path = path
        self.default = make_archive
        self.default_name = path + '.' + self.default.extension
