"""Per-file-type signing implementations."""
import base64
import shutil
import tempfile
from pathlib import Path

from .core import SigningError, _run, extract_pem_from_pfx, list_pkcs12_aliases
from .docx_sign import sign_docx

EMBED_MARKER = b"\n-----BEGIN CERTSIGN SIGNATURE-----\n"
EMBED_END = b"-----END CERTSIGN SIGNATURE-----\n"


def sign_exe(pfx_path, password, infile, outfile, description="Signed with CertSign"):
    """Authenticode-sign a Windows executable using osslsigncode."""
    _run([
        "osslsigncode", "sign",
        "-pkcs12", pfx_path, "-pass", password,
        "-n", description,
        "-in", infile, "-out", outfile,
    ])
    return outfile


def sign_jar(pfx_path, password, infile, outfile, alias=None):
    """Sign a .jar file using jarsigner, treating the .pfx as a PKCS12 keystore."""
    if alias is None:
        aliases = list_pkcs12_aliases(pfx_path, password)
        if not aliases:
            raise SigningError("No private key alias found in the provided certificate.")
        alias = aliases[0]

    _run([
        "jarsigner", "-keystore", pfx_path, "-storetype", "PKCS12",
        "-storepass", password, "-signedjar", outfile,
        infile, alias,
    ])
    return outfile


def sign_pdf(pfx_path, password, infile, outfile):
    """Embed a digital signature into a PDF using pyhanko."""
    _run([
        "pyhanko", "sign", "addsig", "pkcs12",
        "--p12-file", pfx_path, "--p12-pass", password,
        infile, outfile,
    ])
    return outfile


def sign_generic(pfx_path, password, infile, outfile):
    """Fallback for formats with no native embedded signature (png, jpg, docx, ...).

    Produces a detached signature file (outfile) plus a companion .cert.pem
    next to it, so the signature can later be verified against the certificate.
    """
    with tempfile.TemporaryDirectory() as tmp:
        cert_pem, key_pem = extract_pem_from_pfx(pfx_path, password, tmp)
        _run(["openssl", "dgst", "-sha256", "-sign", key_pem, "-out", outfile, infile])
        shutil.copy(cert_pem, str(Path(outfile).with_suffix(Path(outfile).suffix + ".cert.pem")))
    return outfile


def sign_embedded(pfx_path, password, infile, outfile):
    """Sign a file and append the signature + certificate to the same file
    (no separate .sig file), similar to how .exe/.jar/.pdf carry their
    signature inside themselves.

    Only safe for formats where trailing bytes after the "real" content are
    ignored by readers (plain text, and most JPEG/PNG viewers). Never use
    this for container formats like .docx/.zip/.jar - appending bytes after
    their end breaks the archive.
    """
    original = Path(infile).read_bytes()

    with tempfile.TemporaryDirectory() as tmp:
        cert_pem, key_pem = extract_pem_from_pfx(pfx_path, password, tmp)
        orig_path = Path(tmp) / "orig.bin"
        orig_path.write_bytes(original)
        sig_path = Path(tmp) / "sig.bin"
        _run(["openssl", "dgst", "-sha256", "-sign", key_pem, "-out", str(sig_path), str(orig_path)])
        sig_b64 = base64.b64encode(sig_path.read_bytes()).decode("ascii")
        cert_b64 = base64.b64encode(Path(cert_pem).read_bytes()).decode("ascii")

    trailer = EMBED_MARKER + (
        f"Algorithm: RSA-SHA256\n"
        f"Signature: {sig_b64}\n"
        f"Certificate: {cert_b64}\n"
    ).encode("ascii") + EMBED_END

    with open(outfile, "wb") as f:
        f.write(original)
        f.write(trailer)
    return outfile


def verify_embedded(path):
    """Verify a file signed by sign_embedded."""
    data = Path(path).read_bytes()
    idx = data.find(EMBED_MARKER)
    if idx == -1:
        raise SigningError("No embedded CertSign signature found in this file.")

    original = data[:idx]
    trailer_text = data[idx + len(EMBED_MARKER):].decode("ascii", errors="strict")
    fields = {}
    for line in trailer_text.splitlines():
        if line.startswith("-----END"):
            break
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key] = value

    if "Signature" not in fields or "Certificate" not in fields:
        raise SigningError("Signature block is incomplete or corrupted.")

    with tempfile.TemporaryDirectory() as tmp:
        orig_path = Path(tmp) / "orig.bin"
        orig_path.write_bytes(original)
        sig_path = Path(tmp) / "sig.bin"
        sig_path.write_bytes(base64.b64decode(fields["Signature"]))
        cert_path = Path(tmp) / "cert.pem"
        cert_path.write_bytes(base64.b64decode(fields["Certificate"]))
        pubkey = Path(tmp) / "pub.pem"
        _run(["openssl", "x509", "-in", str(cert_path), "-pubkey", "-noout", "-out", str(pubkey)])
        try:
            result = _run([
                "openssl", "dgst", "-sha256", "-verify", str(pubkey),
                "-signature", str(sig_path), str(orig_path),
            ])
        except SigningError:
            return False
        return "Verified OK" in result.stdout


def verify_generic(cert_pem_path, sig_path, infile):
    """Verify a detached signature produced by sign_generic."""
    with tempfile.TemporaryDirectory() as tmp:
        pubkey = str(Path(tmp) / "pub.pem")
        _run(["openssl", "x509", "-in", cert_pem_path, "-pubkey", "-noout", "-out", pubkey])
        result = _run([
            "openssl", "dgst", "-sha256", "-verify", pubkey,
            "-signature", sig_path, infile,
        ])
        return "Verified OK" in result.stdout


SIGNERS = {
    ".exe": ("native", sign_exe),
    ".jar": ("native", sign_jar),
    ".pdf": ("native", sign_pdf),
    ".png": ("embedded", sign_embedded),
    ".jpg": ("embedded", sign_embedded),
    ".jpeg": ("embedded", sign_embedded),
    ".txt": ("embedded", sign_embedded),
    # sign_docx (real Word-compatible OOXML signature via LibreOffice/UNO)
    # exists in docx_sign.py but is NOT wired in here - see its module
    # docstring and README "Experimentell" section for why. Falls back to
    # the proven detached signature until that's resolved.
    ".docx": ("detached", sign_generic),
}


def default_output_path(infile: str, kind: str) -> str:
    p = Path(infile)
    if kind == "detached":
        return str(p.with_name(p.name + ".sig"))
    return str(p.with_name(f"{p.stem}-signed{p.suffix}"))
