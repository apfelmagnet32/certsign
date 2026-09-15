#!/usr/bin/env bash
# Installs CertSign: dependencies, program files, launch command, menu entry.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/lib/certsign"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

install_osslsigncode_aur() {
    if command -v osslsigncode >/dev/null 2>&1; then
        return
    fi
    echo "==> osslsigncode is not in the official Arch repos (AUR only)"
    if command -v yay >/dev/null 2>&1; then
        yay -S --needed --noconfirm osslsigncode
    elif command -v paru >/dev/null 2>&1; then
        paru -S --needed --noconfirm osslsigncode
    else
        echo "No AUR helper (yay/paru) found. Building osslsigncode from the AUR manually:"
        local tmp
        tmp="$(mktemp -d)"
        git clone --depth=1 https://aur.archlinux.org/osslsigncode.git "$tmp"
        (cd "$tmp" && makepkg -si --needed --noconfirm)
        rm -rf "$tmp"
    fi
}

echo "==> Installing system dependencies"
if command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --needed --noconfirm python python-pip tk openssl jdk-openjdk
    install_osslsigncode_aur || echo "Warning: osslsigncode could not be installed - .exe signing won't work, everything else will." >&2
elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-tk python3-pip openssl default-jdk osslsigncode
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-tkinter python3-pip openssl java-latest-openjdk osslsigncode
else
    echo "Unknown distribution: please install python3, tk, openssl, a JDK (jarsigner), and osslsigncode manually." >&2
fi

echo "==> Installing Python dependencies (pyhanko for PDF signing)"
if ! python3 -m pip install --user -r "$SCRIPT_DIR/requirements.txt"; then
    echo "==> pip refused the install (externally-managed-environment), retrying with --break-system-packages"
    python3 -m pip install --user --break-system-packages -r "$SCRIPT_DIR/requirements.txt"
fi

echo "==> Copying program files to $INSTALL_DIR"
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/certsign" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/certsign_gui.py" "$INSTALL_DIR/"

echo "==> Setting up the 'certsign-gui' launch command"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/certsign-gui" <<EOF
#!/bin/sh
exec python3 "$INSTALL_DIR/certsign_gui.py" "\$@"
EOF
chmod +x "$BIN_DIR/certsign-gui"

echo "==> Setting up menu entry"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/certsign.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=CertSign
Comment=Sign files with a self-signed certificate
Exec=$BIN_DIR/certsign-gui
Icon=application-certificate
Terminal=false
Categories=Utility;Security;
EOF

echo
echo "Done. If '$BIN_DIR' is not on your PATH, add it:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "Start with: certsign-gui"
