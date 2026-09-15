# Changelog

All notable changes to CertSign are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.1]

### Fixed
- `generate_self_signed_pfx()` now adds the `extendedKeyUsage=codeSigning`
  extension to generated certificates. Without it, Windows' `WinVerifyTrust`
  rejects the certificate for Authenticode outright — the PKCS7 signature
  on a signed `.exe` is technically valid and unmodified (`osslsigncode
  verify` confirms it), but Explorer's "Digital Signatures" tab either
  doesn't show it or marks it invalid. (Reported by a user testing `.exe`
  signing end to end.)

## [1.0.0]

### Added
- Tkinter GUI (`certsign_gui.py`) for choosing a certificate, a file, and signing it.
- `.exe` signing via Authenticode (`osslsigncode`) — recognized by Windows/SmartScreen.
- `.jar` signing via `jarsigner`, using the `.pfx`/`.p12` directly as a PKCS12 keystore.
- `.pdf` signing via `pyhanko`.
- `.txt`, `.png`, `.jpg` signing: signature + certificate embedded directly at the end of
  the file (no separate file), invalidated by any edit to the file.
- `.docx` signing: detached `<file>.sig` + `.cert.pem`, since these formats have no
  native embedded signature format.
- "Generate new certificate" dialog in the GUI for creating a self-signed `.pfx` on the spot.
- `web/verify.html`: standalone, client-side checker for the embedded signature format
  (`.txt`/`.png`/`.jpg`) — no uploads, verifies in the browser via `node-forge`.
- `install.sh`: one-command install (system + Python dependencies, program files,
  `certsign-gui` launcher, desktop entry) for Arch, Debian/Ubuntu, and Fedora.
- `packaging/arch/PKGBUILD` + desktop entry for `makepkg -si` installs on Arch Linux.
- `certsign/docx_sign.py` (experimental, not wired into the GUI): drives headless
  LibreOffice over UNO to produce a real, Word-compatible OOXML signature for `.docx`.
  Blocked on opening a `.docx` as an OOXML `XStorage`; documented in the README.

### Fixed
- `install.sh` no longer aborts the whole Arch dependency install when `osslsigncode`
  (AUR-only) isn't found in the official repos; it now installs the official packages
  first and handles `osslsigncode` separately via an AUR helper or a manual build.
- `install.sh` now installs `python-pip`/`python3-pip` explicitly (not bundled with
  `python` on Arch/Fedora) and falls back to `--break-system-packages` if pip refuses
  with `externally-managed-environment`.

### Known limitations
- `.docx` does not yet get a native, Word-recognized signature (see `docx_sign.py`).
- `pyhanko`-based `.pdf` signing follows the documented CLI syntax but could not be
  exercised end to end in the environment this was built in.
- All formats signed with the same certificate show the same publisher (its `CN`).
