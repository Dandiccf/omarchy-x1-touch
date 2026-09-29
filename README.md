# X1 Touch

A fingerprint studio for Omarchy and the **ThinkPad X1 Carbon Gen 14**, using
the **Goodix MOC `27c6:659c`** reader. Built as a native Quickshell panel and bar
widget; it follows the active Omarchy palette, font, spacing and corners.

![X1 Touch on the target ThinkPad](preview.png)

## What it does

- Shows the current user's enrolled fingers in a visual left/right selector.
- Enrolls a new finger with live stage counts and placement feedback.
- Tests a specific enrolled finger with match, retry and timeout feedback.
- Removes one selected finger after an explicit confirmation.
- Offers configurable test/enrollment timeouts, animation, hints and default hand.
- Shows hardware, driver versions and detected sudo/Polkit/lock configuration.
- Supports keyboard focus with Tab, activation with Enter/Space, and Escape to
  cancel a scan or close the panel. Closing the panel releases its reader claim.
- Adds an application launcher and a fingerprint button on the Omarchy bar.

The fingerprint drawing is an illustration. The plugin receives status events
from fprintd, not fingerprint images, templates, confidence scores or passwords.
Enrollment progress counts successful stages reported by the reader. The test
progress line represents elapsed time, not fingerprint quality.

## Requirements

- Omarchy 4.x with the Quickshell plugin system (developed on 4.0.4).
- USB reader `27c6:659c` and fprintd exposing `Goodix MOC Fingerprint Sensor`.
- Existing working `fprintd` and `libfprint`/`libfprint-git` installation.
- `/usr/bin/python`, `python-gobject`, GTK/GLib introspection, and `pacman`.
- Active desktop session with a Polkit authentication agent (Omarchy provides it).

This project uses the existing driver. It does not flash firmware, replace
libfprint, install an authentication service, or rewrite PAM. It rejects other
USB models, including the T480's Synaptics reader. If multiple Goodix devices
are exposed, it refuses to guess which one owns an enrollment.

## Install

With the supported reader already working through fprintd:

```bash
omarchy pkg add fprintd python-gobject
omarchy plugin add https://github.com/Dandiccf/omarchy-x1-touch --enable
```

Click the fingerprint bar icon to open the studio. To also add an application
launcher entry, run this optional command after installation:

```bash
/usr/bin/python ~/.config/omarchy/plugins/io.github.dandiccf.x1-touch/scripts/install.py launcher
```

Plugin ID: `io.github.dandiccf.x1-touch`. The plugin does not install or replace
your fingerprint driver. This first release has automated tests and live
hardware timeout/cancellation validation; see [validation status](VALIDATION.md)
for physical enrollment and matching checks still to be completed.

## Install from a development checkout

From this project checkout:

```bash
/usr/bin/python scripts/install.py install
```

This copies a validated plugin to `~/.config/omarchy/plugins/io.github.dandiccf.x1-touch`,
registers the launcher, and enables the bar widget. Updating with the same
command saves the previous plugin in `~/.local/state/x1-touch/install-backups/`.
It requires no sudo. Keep the project checkout as the editable source.
If a plugin update retains an old layout in memory, run `omarchy restart shell`
once after closing any active scan; this refreshes the shell’s QML cache.

Open **X1 Touch** in the application launcher, click the fingerprint bar icon, or:

```bash
omarchy-shell shell summon io.github.dandiccf.x1-touch '{}'
```

Marketplace installs are ordinary Git checkouts and can be updated with
`omarchy plugin update io.github.dandiccf.x1-touch`. The local development
installer copies files instead; it intentionally does not copy Git metadata.

## Use

Select a hand and finger. A filled dot means an enrollment exists for your
current Linux account. Empty fingers offer **Enroll fingerprint**; registered
fingers offer **Test fingerprint** and **Remove**. Enrollment never silently
replaces an existing entry. Removing a finger is permanent and requires a new
enrollment to restore it. There is no bulk-clear action.

For enrollment, approve the system authorization dialog if it appears, then
touch and fully lift your finger between stages. The panel displays the actual
stage count reported by fprintd. You can cancel at any time. A completed
enrollment remains saved even if you close the panel immediately afterwards.
Goodix/fprintd owns incomplete-enrollment cleanup and sensor storage.

The list covers the current Linux user's registrations known to fprintd. It is
not an inventory of other users' or Windows Hello's sensor entries.

Preferences are stored atomically with mode `0600` in
`~/.config/x1-touch/settings.json` (XDG paths are respected). Scan timeouts apply
only to this plugin; they do not alter sudo or the lock screen's timeout.
Authentication badges report directly configured `pam_fprintd.so` lines, not
successful authentication tests or recursive PAM-stack analysis.

## Terminal interface

```bash
/usr/bin/python backend/fingerprint.py status
/usr/bin/python backend/fingerprint.py verify --finger right-index-finger
/usr/bin/python backend/fingerprint.py enroll --finger left-index-finger
```

Output is newline-delimited JSON. Operates only as the current user, using
fprintd's empty-username convention. Deletion additionally requires
`--confirm-finger` to match `--finger`. The helper does not bypass Polkit.

## Development and checks

```bash
bash scripts/check.sh
```

Tests cover exact USB matching, input validation, configuration persistence,
enrollment progress, duplicate-enrollment refusal, confirmation requirements,
match/failure, timeout, cancellation and reader release. These tests use a fake
fprintd client and never add or remove fingerprints on real hardware.

`backend/model.py` owns pure validation/state. `backend/fingerprint.py` is the
Gio D-Bus bridge. `Controller.qml` consumes its JSON events. `Panel.qml` and
`components/` contain the native themed UI. There is no always-on polling daemon;
status refreshes when the panel opens, after an operation, or on Refresh.

See [VALIDATION.md](VALIDATION.md) for the checks performed on the target laptop.

Before release, manually test an enrollment with a spare finger, successful
verification, cancellation, per-finger deletion, Polkit denial, busy reader,
sleep/resume, and a small/high-DPI screen. Successful matching and enrollment
require a person's physical touch and cannot be established by unit tests.

API reference: [fprintd Device interface](https://fprint.freedesktop.org/fprintd-dev/Device.html).
Shell contract: `/usr/share/omarchy/shell/README.md` on the target system.

## Remove

From the installed plugin or a source checkout:

```bash
/usr/bin/python ~/.config/omarchy/plugins/io.github.dandiccf.x1-touch/scripts/install.py uninstall --yes
```

This removes the plugin, launcher and icon. Existing fingerprints, authentication
configuration and your preferences are retained.

If you did not register the optional launcher, `omarchy plugin remove
io.github.dandiccf.x1-touch` also removes the standard plugin checkout.

## License

MIT. Original implementation; no T480 project driver or code is bundled.
