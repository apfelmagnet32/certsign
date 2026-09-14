# CertSign

GUI-Tool fuer Linux, um Dateien mit einem (selbstsignierten) Zertifikat zu
signieren. Du gibst ein Zertifikat (`.pfx`/`.p12`, Cert + Private Key) und
eine Datei an, das Tool erkennt den Dateityp und signiert entsprechend.

## Unterstuetzte Dateitypen

| Typ | Verfahren | Ergebnis |
|---|---|---|
| `.exe` | Authenticode via `osslsigncode` | Signatur ist in der `.exe` eingebettet, Windows/SmartScreen erkennt eine Signatur ("Herausgeber: unbekannt" bei selbstsigniertem Zertifikat) |
| `.jar` | `jarsigner` | Signatur ist im Jar eingebettet, von der JVM pruefbar |
| `.pdf` | `pyhanko` | Digitale Signatur ist im PDF eingebettet |
| `.png`, `.jpg`, `.txt` | OpenSSL, eingebettet | Signatur + Zertifikat werden als Textblock ans Ende der Datei angehaengt (kein separates File). Datei bleibt normal nutzbar, jede Aenderung macht die Signatur ungueltig. |
| `.docx` | OpenSSL, detached | Kein natives Signaturformat aktiv genutzt (siehe "Experimentell" unten). Es wird eine separate `<datei>.sig` (+ `.cert.pem`) danebengelegt. |

Da alle Formate mit demselben Zertifikat signiert werden, zeigen sie auch
alle denselben Herausgeber (das `CN` aus dem Zertifikat-Subject).

## Signatur-Checker (Browser)

`web/verify.html` ist eine eigenstaendige, clientseitige Seite, die eine
mit CertSign eingebettet signierte Datei (`.txt`/`.png`/`.jpg`) prueft:
sucht den `CERTSIGN SIGNATURE`-Block, verifiziert die RSA-SHA256-Signatur
gegen das eingebettete Zertifikat (via `node-forge`). Laeuft komplett im
Browser, keine Uploads. Einfach lokal im Browser oeffnen oder hosten.

## Experimentell: echte Word-Signatur fuer .docx

`certsign/docx_sign.py` enthaelt einen Ansatz, der `.docx`-Dateien ueber
headless LibreOffice (UNO-Automatisierung) mit einer echten, Word-kompatiblen
OOXML-Signatur versieht (dieselbe Art, die Word unter "Datei > Informationen
> Digitale Signatur hinzufuegen" erzeugt) - statt einer externen `.sig`.

**Der Code ist nicht in die GUI eingebunden**, weil er bislang an einer
einzigen Stelle scheitert: `.docx` als `com.sun.star.embed.XStorage` im
OOXML-Format (statt ODF mit `META-INF/manifest.xml`) zu oeffnen. Mehrere
bekannte Property-Varianten werden automatisch durchprobiert
(`_uno_sign_docx.py`, `open_ooxml_storage()`), scheitern aber alle mit
`Can not open storage!`. Alles andere funktioniert nachweislich: NSS-Cert-
Import, UNO-Verbindung zu headless LibreOffice, Zertifikat-Abruf daraus.

Falls du das zum Laufen bringst (oder die richtige `StorageFormat`/
`PackageFormat`-Property kennst): `certsign/_uno_sign_docx.py` anpassen,
dann in `certsign/signers.py` die `.docx`-Zeile in `SIGNERS` auf
`("native", sign_docx)` umstellen.

Zum Testen (braucht `libreoffice-writer`, `python3-uno`, `libnss3-tools`):

```python
from certsign.docx_sign import sign_docx
sign_docx("cert.pfx", "password", "in.docx", "out.docx")
```

## Abhaengigkeiten (Linux)

```bash
sudo apt install osslsigncode python3-tk default-jdk openssl
pip install -r requirements.txt   # pyhanko
```

## Nutzung

```bash
python3 certsign_gui.py
```

1. Zertifikat (`.pfx`/`.p12`) auswaehlen + Passwort eingeben
2. Zu signierende Datei auswaehlen
3. Ausgabepfad pruefen/anpassen
4. "Signieren" klicken

## Installation auf Arch Linux

```bash
cd packaging/arch
makepkg -si
```

Baut und installiert `certsign` als Paket; danach per `certsign-gui` oder
ueber den Anwendungsstarter ("CertSign") aufrufbar. `python-pyhanko` (fuer
PDF-Signierung) liegt im AUR und muss ggf. separat installiert werden
(`yay -S python-pyhanko`).

## Verifikation

Eingebettete Signaturen (png/jpg/txt) pruefen:

```python
from certsign.signers import verify_embedded
verify_embedded("datei-signed.ext")  # True/False
```

Detached Signaturen (docx) pruefen:

```bash
openssl x509 -in datei.ext.sig.cert.pem -pubkey -noout > pub.pem
openssl dgst -sha256 -verify pub.pem -signature datei.ext.sig datei.ext
```
