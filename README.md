# DwarvenArchive

A fast, minimal GTK4 archive manager. Part of the [DwarvenSuite](https://github.com/gitdwarf).

Spiritual successor to ROX Archive. Same one-click workflow, pure GTK4, no legacy dependencies.

## What it does

Pass DwarvenArchive a file or folder -- it opens, you pick a destination and format, click Save. Done.
Pass it an archive -- pick a destination, click Save. Done.
No second dialog. No hunting through menus. One window, one click.

Works via right-click in any file manager that supports Open With or custom actions.

Each launch is fully independent -- multiple concurrent archive and extraction operations work without interference, just like ROX Archive.

If an operation fails, a dialog shows the error -- including the exact command, exit code, and tool output -- so you know what went wrong.

## Supported formats

**Create archives** (from a folder, file, or multiple files/folders): ZIP (password), Tar+gzip, Tar+bzip2, Tar+xz, Tar+lzma, Tar, 7-Zip (password), JAR (password), LHA

**Compress single files**: gzip, bzip2, xz, lzma, UUencode

**Extract**: ZIP, TGZ, TAR.BZ2, TAR.Z, TLZ, TXZ, RAR, ACE, TAR, RPM, CPIO, DEB, JAR, LHA, 7Z

Password-protected extraction: ZIP, JAR, 7Z

Formats requiring tools that are not installed simply do not appear in the format list.

## Installation

```bash
pip install dwarvenarchive
```

On first launch, DwarvenArchive automatically installs its icon and desktop file. No manual setup required.

## Usage

```bash
dwarvenarchive /path/to/folder           # Archive a directory
dwarvenarchive file1.txt file2.png dir/  # Archive multiple files/folders together
dwarvenarchive /path/to/archive.tgz     # Extract an archive
dwarvenarchive -                         # Read from stdin
```

When launched with a directory or file -- presents the archive/extraction dialog.
When launched with multiple paths -- presents archive creation dialog for all of them combined, using the first filename as the output name.
When launched with no arguments -- shows the launch window. From there you can drag and drop one or more files, folders, or archives directly onto the window. Files accumulate as you drop them; the operation starts automatically once drops stop arriving.

Drag and drop is compatible with GTK2, GTK3, and GTK4 file managers (tested with ROXFiler and Thunar).

## Dependencies

Required: Python 3.9+, GTK 4.0, PyGObject (python3-gi)

Optional (enables additional formats): gzip, bzip2, xz, lzma, tar (usually pre-installed), zip/unzip, 7z (p7zip-full), unrar, unace, lha (lhasa), rpm2cpio

## Part of DwarvenSuite

All tools follow the same philosophy: small, fast, correct, as few dependencies as possible!

## Author

thedwarf -- gitdwarf

## Support / Tip Jar

If you find DwarvenArchive useful, you can support the project:

[![Donate via PayPal](https://img.shields.io/badge/Donate-PayPal-blue?logo=paypal)](https://www.paypal.com/paypalme/gitdwarf)

## License

GPL-2.0-or-later -- same as ROX Archive, whose workflow inspired this tool.
