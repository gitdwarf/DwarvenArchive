# DwarvenArchive Changelog

## 1.1.0

- Multiple concurrent instances: each launch is now fully independent,
  allowing any number of archive/extraction operations to run simultaneously
  without interference -- matching the original ROX Archive behaviour.
- Progress bar: fixed scanner animation for GTK4 (uses frame clock correctly).
- False password detection: tightened ZIP encryption check to avoid false
  positives on unencrypted archives.
- Destination exists dialog: clearer message and correct behaviour when
  extraction destination already exists.
- Delete source: now works correctly for all data types including directories
  (uses rmtree) and multiple files.

## 1.0.2 / 1.0.1

- Multi-file support: CLI and drag-and-drop both support multiple files and
  folders archived together in a single operation.
- Single files now correctly show archive format options (zip, tgz, etc)
  not just compress options.
- Default format selection is dynamic based on installed tools and list order.
- Unavailable tools filtered from format list.
- Info window refactored into its own module with drag-and-drop support.
- Drag-and-drop compatible with GTK2, GTK3, and GTK4 file managers.
- Drop settle timer for accumulating multi-file drags.
- Delete source fixed to use actual file path (not sys.argv).

## 1.0.0

Initial release. GTK4 spiritual successor to ROX Archive.
