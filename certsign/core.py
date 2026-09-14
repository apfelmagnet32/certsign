"""Shared helpers for working with PKCS#12 (.pfx/.p12) certificate bundles."""
import re
import subprocess
import tempfile
from pathlib import Path


class SigningError(RuntimeError):
    """Raised when an external signing tool fails."""


def _run(cmd, **kwargs):
    result = subprocess.run(
        cmd, capture_output=True, text=True, **kwargs
    )
    if result.returncode != 0:
        raise SigningError(
            f"Command failed ({' '.join(cmd[:2])}...): {result.stderr or result.stdout}"
        )
    return result


def extract_pem_from_pfx(pfx_path: str, password: str, workdir: str):
    """Extract cert.pem and key.pem from a PKCS#12 bundle into workdir. Returns (cert_pem, key_pem)."""
    cert_pem = str(Path(workdir) / "cert.pem")
    key_pem = str(Path(workdir) / "key.pem")

    _run([
        "openssl", "pkcs12", "-in", pfx_path, "-clcerts", "-nokeys",
        "-out", cert_pem, "-passin", f"pass:{password}",
    ])
    _run([
        "openssl", "pkcs12", "-in", pfx_path, "-nocerts", "-nodes",
        "-out", key_pem, "-passin", f"pass:{password}",
    ])
    return cert_pem, key_pem


def list_pkcs12_aliases(pfx_path: str, password: str):
    """Return the list of key aliases found in a PKCS#12 keystore."""
    result = _run([
        "keytool", "-list", "-keystore", pfx_path,
        "-storetype", "PKCS12", "-storepass", password,
    ])
    aliases = []
    for line in result.stdout.splitlines():
        m = re.match(r"^([^,]+), .*, PrivateKeyEntry", line)
        if m:
            aliases.append(m.group(1))
    return aliases


def generate_self_signed_pfx(out_pfx: str, password: str, common_name: str, workdir: str, days: int = 365):
    """Generate a fresh self-signed certificate + key and package it as a .pfx."""
    key_pem = str(Path(workdir) / "gen_key.pem")
    cert_pem = str(Path(workdir) / "gen_cert.pem")

    _run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", key_pem, "-out", cert_pem, "-days", str(days),
        "-subj", f"/CN={common_name}",
    ])
    _run([
        "openssl", "pkcs12", "-export", "-out", out_pfx,
        "-inkey", key_pem, "-in", cert_pem,
        "-passout", f"pass:{password}", "-name", common_name,
    ])
    return out_pfx
