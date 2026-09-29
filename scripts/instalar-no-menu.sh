#!/usr/bin/env bash
# Põe a Clarisse no menu de aplicativos do GNOME. Rode de dentro da pasta onde ela vai ficar.
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
destino="$HOME/.local/share/applications/clarisse.desktop"

mkdir -p "$(dirname "$destino")"
cat > "$destino" <<EOF
[Desktop Entry]
Type=Application
Name=Clarisse
Comment=Assistente de voz local
Exec=ptyxis --new-window -d "$raiz" -- "$raiz/scripts/ligar.sh"
Icon=$raiz/web/icone.svg
Terminal=false
Categories=Utility;
EOF

echo "Clarisse no menu de aplicativos: $destino"
