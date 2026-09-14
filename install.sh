#!/usr/bin/env bash
# Installiert CertSign: Abhaengigkeiten, Programmdateien, Startbefehl, Menueintrag.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/lib/certsign"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

install_osslsigncode_aur() {
    if command -v osslsigncode >/dev/null 2>&1; then
        return
    fi
    echo "==> osslsigncode ist nicht in den offiziellen Arch-Repos (nur AUR)"
    if command -v yay >/dev/null 2>&1; then
        yay -S --needed --noconfirm osslsigncode
    elif command -v paru >/dev/null 2>&1; then
        paru -S --needed --noconfirm osslsigncode
    else
        echo "Kein AUR-Helper (yay/paru) gefunden. Baue osslsigncode manuell aus dem AUR:"
        local tmp
        tmp="$(mktemp -d)"
        git clone --depth=1 https://aur.archlinux.org/osslsigncode.git "$tmp"
        (cd "$tmp" && makepkg -si --needed --noconfirm)
        rm -rf "$tmp"
    fi
}

echo "==> Installiere Systemabhaengigkeiten"
if command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --needed --noconfirm python python-pip tk openssl jdk-openjdk
    install_osslsigncode_aur || echo "Warnung: osslsigncode konnte nicht installiert werden - .exe-Signierung wird nicht funktionieren, der Rest schon." >&2
elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-tk python3-pip openssl default-jdk osslsigncode
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-tkinter python3-pip openssl java-latest-openjdk osslsigncode
else
    echo "Unbekannte Distribution: bitte python3, tk, openssl, JDK (jarsigner) und osslsigncode manuell installieren." >&2
fi

echo "==> Installiere Python-Abhaengigkeiten (pyhanko fuer PDF-Signierung)"
if ! python3 -m pip install --user -r "$SCRIPT_DIR/requirements.txt"; then
    echo "==> pip verweigert die Installation (externally-managed-environment), versuche --break-system-packages"
    python3 -m pip install --user --break-system-packages -r "$SCRIPT_DIR/requirements.txt"
fi

echo "==> Kopiere Programmdateien nach $INSTALL_DIR"
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/certsign" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/certsign_gui.py" "$INSTALL_DIR/"

echo "==> Richte Startbefehl 'certsign-gui' ein"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/certsign-gui" <<EOF
#!/bin/sh
exec python3 "$INSTALL_DIR/certsign_gui.py" "\$@"
EOF
chmod +x "$BIN_DIR/certsign-gui"

echo "==> Richte Menueintrag ein"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/certsign.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=CertSign
Comment=Dateien mit einem selbstsignierten Zertifikat signieren
Exec=$BIN_DIR/certsign-gui
Icon=application-certificate
Terminal=false
Categories=Utility;Security;
EOF

echo
echo "Fertig. Falls '$BIN_DIR' nicht in deinem PATH ist, fuege es hinzu:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "Start mit: certsign-gui"
