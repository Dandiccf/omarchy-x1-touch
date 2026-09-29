# Changelog

## 0.2.0 — 2026-09-29

- Discover readers through fprintd without a ThinkPad, vendor or USB-ID whitelist.
- Display the actual reader and scan method, with press/swipe guidance.
- Retain the one-reader limit and confirmed single-finger deletion.
- Document upstream compatibility separately from physical validation.
- Protect foreign launcher/icon files and symlinks during setup and removal.
- Preserve the plugin ID, settings and existing bar placement.

## 0.1.0 — 2026-09-29

Initial public release for the ThinkPad X1 Carbon Gen 14 Goodix MOC `27c6:659c`.

- Native Omarchy panel, bar icon and optional application launcher.
- Visual finger selection and current-user enrollment listing.
- Enrollment, verification and confirmed single-finger removal through fprintd.
- Real scan feedback, cancellation, timeouts and reader-claim cleanup.
- Persistent preferences, theme integration and hardware/authentication status.
- Unit tests and documented real-hardware validation limits.
