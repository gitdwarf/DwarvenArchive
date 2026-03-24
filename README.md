# DwarvenArchive

A fast, minimal GTK4 archive manager. Part of the [DwarvenSuite](https://github.com/gitdwarf).

Spiritual successor to ROX Archive. Same one-click workflow, pure GTK4, no legacy dependencies.

## What it does

Pass DwarvenArchive a file or folder -- it opens, you pick a destination and format, click Save. Done.
Pass it an archive -- pick a destination, click Save. Done.
No second dialog. No hunting through menus. One window, one click.

Works via right-click in any file manager that supports Open With or custom actions.

## Supported formats

**Create archives** (from a folder or file): ZIP (password), Tar+gzip, Tar+bzip2, Tar+xz, Tar+lzma, Tar, 7-Zip (password), JAR (password), LHA

**Compress single files**: gzip, bzip2, xz, lzma, UUencode

**Extract**: ZIP, TGZ, TAR.BZ2, TAR.Z, TLZ, TXZ, RAR, ACE, TAR, RPM, CPIO, DEB, JAR, LHA, 7Z

Password-protected extraction: ZIP, JAR, 7Z

## Installation

```bash
pip install dwarvenarchive
```

On first launch, DwarvenArchive automatically installs its icon and desktop file. No manual setup required.

## Usage

```bash
dwarvenarchive /path/to/folder        # Archive a directory
dwarvenarchive /path/to/file.txt      # Archive a file
dwarvenarchive /path/to/archive.tgz  # Extract an archive
dwarvenarchive -                      # Read from stdin
```

When launched with a directory -- presents archive creation dialog.
When launched with a file -- presents extraction or compression dialog depending on type.
When launched with no arguments -- shows usage info.

## Dependencies

Required: Python 3.9+, GTK 4.0, PyGObject (python3-gi)

Optional (enables additional formats): gzip, bzip2, xz, lzma, tar (usually pre-installed), zip/unzip, 7z (p7zip-full), unrar, unace, lha (lhasa), rpm2cpio

DwarvenArchive gracefully handles missing tools -- formats requiring unavailable tools simply don't appear in the format list.

## Part of DwarvenSuite

All tools follow the same philosophy: small, fast, correct, as few dependencies as possible!

## Author

thedwarf -- gitdwarf

## Support / Tip Jar

If you find DwarvenArchive useful, you can support the project:

[![Donate via PayPal](https://img.shields.io/badge/Donate-PayPal-blue?logo=paypal)](https://www.paypal.com/paypalme/gitdwarf)

## License

GPL-2.0-or-later -- same as ROX Archive, whose workflow inspired this tool.
