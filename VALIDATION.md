# Validation — 2026-09-29

Target: ThinkPad X1 Carbon Gen 14, Omarchy 4.0.4, Goodix MOC USB 27c6:659c.

## Completed

- Omarchy manifest validation.
- 30 Python tests: generic discovery (Goodix, Synaptics, swipe and SPI readers),
  absent/multiple/disconnected devices, swipe feedback, preferences and atomic writes, scan
  event semantics, startup cancellation race, cleanup after completion/error,
  timeout, per-finger deletion contract, confirmation, asynchronous plugin
  discovery, launcher identity, foreign-file/symlink preservation and installer safeguards.
- Python syntax checks and QML lint. The check script documents the three
  unavoidable host type-metadata categories excluded from static lint.
- Read-only live hardware discovery and enrollment listing.
- Live verification start: reader reports 9 enrollment stages.
- Live five-second timeout, VerifyStop and Release.
- Live cancellation immediately after scan start, VerifyStop and Release.
- Confirmed existing right-index enrollment is unchanged after these tests.
- Installed helper returns the same hardware/enrollment data as the source copy.
- Installed plugin enabled in Omarchy with bar icon and valid desktop launcher.
- Visual review at 2880×1800, 2× display scale; native theme and final layout load
  correctly after a shell restart. No plugin-specific runtime errors observed.

## Compatibility limits

Release 0.2.0 removes the hardware whitelist. Non-Goodix, swipe and SPI readers
have simulated coverage only, not physical validation. Only one reader may be
exposed by fprintd at a time. Upstream support does not guarantee that an installed
driver version supports a device. See the README compatibility table.

## Physical checks still required

- A successful match with the owner's actual finger.
- Enrollment of a spare finger and single-finger removal.
- Polkit denial, concurrent reader use, and sleep/resume during a scan.

Tests do not silently enroll or delete real fingerprints. Authentication badges
report configuration, not end-to-end sudo or lock-screen tests.
