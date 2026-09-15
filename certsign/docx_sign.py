"""Word-compatible OOXML digital signature for .docx via headless LibreOffice.

LibreOffice implements the real ECMA-376 OOXML signature format (XML-DSig
embedded in the package), the same one Word uses and recognizes under
"File > Info > Protect Document > Add a Digital Signature". Rather than
hand-rolling that XML structure (high risk of producing something Word
rejects), this drives LibreOffice itself to do the signing.

CAVEAT: this could not be end-to-end verified in the sandbox this was
written in - headless LibreOffice there failed to even convert a plain
.txt to PDF, which points at a broken/incomplete LibreOffice install in
that environment rather than a problem with this approach. Test on your
own machine; failures surface as SigningError with the underlying cause.
"""
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from .core import SigningError, _run

_UNO_SCRIPT = Path(__file__).with_name("_uno_sign_docx.py")
_SOFFICE_PORT = 2002

_UNO_PYTHON_CANDIDATES = (
    "/usr/lib/libreoffice/program/python3",
    "/usr/lib/libreoffice/program/python",
    "python3",
)


def _find_uno_python():
    for candidate in _UNO_PYTHON_CANDIDATES:
        try:
            result = subprocess.run(
                [candidate, "-c", "import uno"], capture_output=True
            )
        except FileNotFoundError:
            continue
        if result.returncode == 0:
            return candidate
    raise SigningError(
        "No Python with UNO bindings found. Install 'python3-uno' "
        "(Debian/Ubuntu) or your distribution's LibreOffice SDK packages."
    )


def _build_nss_db(pfx_path, password, nss_dir):
    _run(["certutil", "-N", "-d", f"sql:{nss_dir}", "--empty-password"])
    _run(["pk12util", "-d", f"sql:{nss_dir}", "-i", pfx_path, "-W", password, "-K", ""])


def _wait_for_port(host, port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise SigningError("LibreOffice did not become reachable on the UNO socket after starting.")


def sign_docx(pfx_path, password, infile, outfile):
    """Sign a .docx with a real, Word-compatible embedded digital signature."""
    py = _find_uno_python()

    with tempfile.TemporaryDirectory() as tmp:
        nss_dir = str(Path(tmp) / "nssdb")
        lo_profile = str(Path(tmp) / "lo_profile")
        os.makedirs(nss_dir, exist_ok=True)
        os.makedirs(lo_profile, exist_ok=True)

        _build_nss_db(pfx_path, password, nss_dir)

        if str(Path(infile).resolve()) != str(Path(outfile).resolve()):
            shutil.copy(infile, outfile)

        env = os.environ.copy()
        env["MOZILLA_CERTIFICATE_FOLDER"] = nss_dir
        env["HOME"] = lo_profile

        proc = subprocess.Popen(
            [
                "soffice", "--headless", "--invisible", "--nocrashreport",
                "--nodefault", "--nologo", "--norestore",
                f"-env:UserInstallation=file://{lo_profile}/profile",
                f"--accept=socket,host=localhost,port={_SOFFICE_PORT};urp;",
            ],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        try:
            _wait_for_port("localhost", _SOFFICE_PORT, timeout=30)
            time.sleep(2)  # socket is up before UNO services are fully registered

            result = subprocess.run(
                [py, str(_UNO_SCRIPT), str(Path(outfile).resolve()), str(_SOFFICE_PORT)],
                env=env, capture_output=True, text=True,
            )
            if result.returncode != 0:
                raise SigningError(
                    "LibreOffice signing failed: "
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    return outfile
