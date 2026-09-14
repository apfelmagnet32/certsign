# CertSign

GUI tool for Linux that signs files with a (self-signed) certificate. You
provide a certificate (`.pfx`/`.p12`, cert + private key) and a file; the
tool detects the file type and signs it accordingly.

## Supported file types

| Type | Method | Result |
|---|---|---|
| `.exe` | Authenticode via `osslsigncode` | Signature is embedded in the `.exe`; Windows/SmartScreen recognizes a signature ("Publisher: unknown" for a self-signed certificate) |
| `.jar` | `jarsigner` | Signature is embedded in the jar, verifiable by the JVM |
| `.pdf` | `pyhanko` | Digital signature is embedded in the PDF |
| `.png`, `.jpg`, `.txt` | OpenSSL, embedded | Signature + certificate are appended as a text block to the end of the file (no separate file). File stays usable as normal; any change invalidates the signature. |
| `.docx` | OpenSSL, detached | No native signature format actively used (see "Experimental" below). A separate `<file>.sig` (+ `.cert.pem`) is placed next to it. |

Since all formats are signed with the same certificate, they all show the
same publisher (the `CN` from the certificate subject).

## Signature checker (browser)

`web/verify.html` is a standalone, client-side page that verifies a file
CertSign signed with the embedded scheme (`.txt`/`.png`/`.jpg`): it finds
the `CERTSIGN SIGNATURE` block and verifies the RSA-SHA256 signature
against the embedded certificate (via `node-forge`). Runs entirely in the
browser, no uploads. Just open it locally in a browser or host it.

## Experimental: real Word signature for .docx

`certsign/docx_sign.py` contains an approach that embeds a real,
Word-compatible OOXML signature into `.docx` files via headless
LibreOffice (UNO automation) - the same kind Word produces under
"File > Info > Add a Digital Signature" - instead of an external `.sig`.

**The code is not wired into the GUI** because it currently fails at one
spot: opening the `.docx` as a `com.sun.star.embed.XStorage` in OOXML
format (instead of ODF with `META-INF/manifest.xml`). Several known
property variants are tried automatically (`_uno_sign_docx.py`,
`open_ooxml_storage()`), but all of them fail with `Can not open
storage!`. Everything else works, verifiably: NSS cert import, UNO
connection to headless LibreOffice, certificate lookup from it.

If you get this working (or know the correct `StorageFormat`/
`PackageFormat` property): adjust `certsign/_uno_sign_docx.py`, then in
`certsign/signers.py` change the `.docx` line in `SIGNERS` to
`("native", sign_docx)`.

To test (needs `libreoffice-writer`, `python3-uno`, `libnss3-tools`):

```python
from certsign.docx_sign import sign_docx
sign_docx("cert.pfx", "password", "in.docx", "out.docx")
```

## Dependencies (Linux)

```bash
sudo apt install osslsigncode python3-tk default-jdk openssl
pip install -r requirements.txt   # pyhanko
```

## Usage

```bash
python3 certsign_gui.py
```

1. Choose a certificate (`.pfx`/`.p12`) + enter the password
2. Choose the file to sign
3. Check/adjust the output path
4. Click "Sign"

## Installing on Arch Linux

```bash
cd packaging/arch
makepkg -si
```

Builds and installs `certsign` as a package; afterwards launch it via
`certsign-gui` or from the application launcher ("CertSign").
`python-pyhanko` (for PDF signing) lives in the AUR and may need to be
installed separately (`yay -S python-pyhanko`).

## Verification

Check embedded signatures (png/jpg/txt):

```python
from certsign.signers import verify_embedded
verify_embedded("file-signed.ext")  # True/False
```

Check detached signatures (docx):

```bash
openssl x509 -in file.ext.sig.cert.pem -pubkey -noout > pub.pem
openssl dgst -sha256 -verify pub.pem -signature file.ext.sig file.ext
```
