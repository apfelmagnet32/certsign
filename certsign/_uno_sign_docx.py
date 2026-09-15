"""Executed under a UNO-capable Python interpreter (usually the system
python3 with the python3-uno bridge installed, NOT the app's own venv).

Connects to an already-running headless LibreOffice instance and embeds a
real, Word-compatible OOXML digital signature into a .docx, using the
certificate found in whatever NSS store LibreOffice was pointed at via
MOZILLA_CERTIFICATE_FOLDER.

KNOWN OPEN ISSUE: opening the .docx as a com.sun.star.embed.XStorage in
OOXML (not ODF) format requires telling the StorageFactory the package
isn't ODF-style (which expects a META-INF/manifest.xml a .docx doesn't
have). Several property spellings for that are tried below
(_STORAGE_ARG_STRATEGIES); if all of them fail on your LibreOffice
version, this will raise with the underlying UNO error message - please
report back what worked/didn't so this list can be corrected.

Usage: _uno_sign_docx.py <path-to-docx> <uno-port>
"""
import sys
import time

import uno
from com.sun.star.beans import PropertyValue

READWRITE = 3
TRUNCATE = 8


def make_prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


def connect(port):
    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_ctx)
    last_err = None
    for _ in range(30):
        try:
            return resolver.resolve(
                f"uno:socket,host=localhost,port={port};urp;StarOffice.ComponentContext")
        except Exception as e:  # noqa: BLE001 - want to retry on any connection error
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"Connection to LibreOffice (port {port}) failed: {last_err}")


def open_ooxml_storage(storage_factory, url):
    """Try several known ways to tell LibreOffice "this zip is OOXML, not
    an ODF package with a manifest" - LO versions differ on the exact
    property spelling, so we try a few in order and keep the last error.
    """
    strategies = [
        ("PackageFormat=False (2-arg PropertyValue)", lambda: storage_factory.createInstanceWithArguments(
            (url, READWRITE, (make_prop("PackageFormat", False),)))),
        ("StorageFormat=OFOPXMLFormat", lambda: storage_factory.createInstanceWithArguments(
            (url, READWRITE, (make_prop("StorageFormat", "OFOPXMLFormat"),)))),
        ("StorageFormat=ZipFormat", lambda: storage_factory.createInstanceWithArguments(
            (url, READWRITE, (make_prop("StorageFormat", "ZipFormat"),)))),
        ("plain (url, READWRITE)", lambda: storage_factory.createInstanceWithArguments((url, READWRITE))),
    ]
    last_err = None
    for label, attempt in strategies:
        try:
            storage = attempt()
            # Creation can succeed lazily; force real access now so a bad
            # format choice fails here, not deep inside signing.
            storage.getElementNames()
            return storage, label
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise RuntimeError(
        f"Could not open the .docx as an OOXML storage (all strategies failed). "
        f"Last error: {last_err}"
    )


def main(path, port):
    ctx = connect(port)
    smgr = ctx.ServiceManager

    se_init = smgr.createInstanceWithContext("com.sun.star.xml.crypto.SEInitializer", ctx)
    sec_ctx = se_init.createSecurityContext("")
    sec_env = sec_ctx.getSecurityEnvironment()
    certs = sec_env.getPersonalCertificates()
    if not certs:
        raise RuntimeError("No certificate found in the given NSS database.")
    cert = certs[0]

    sig = smgr.createInstanceWithContext(
        "com.sun.star.security.DocumentDigitalSignatures", ctx)
    stream_name = sig.getDocumentContentSignatureDefaultStreamName()

    url = "file://" + path
    storage_factory = smgr.createInstanceWithContext("com.sun.star.embed.StorageFactory", ctx)
    storage, used_strategy = open_ooxml_storage(storage_factory, url)
    sys.stderr.write(f"[info] OOXML storage opened using strategy: {used_strategy}\n")

    stream = storage.openStreamElement(stream_name, READWRITE | TRUNCATE)
    ok = sig.signDocumentWithCertificate(cert, storage, stream)
    if not ok:
        raise RuntimeError("signDocumentWithCertificate() did not produce a signature.")

    storage.commit()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
