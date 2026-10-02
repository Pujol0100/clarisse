#!/usr/bin/env bash
# Cadastra no GNOME o atalho que liga e desliga o microfone da Clarisse.
# Uso: scripts/instalar-atalho.sh [combinação]   (padrão: Insert; outra, por exemplo: "<Primary><Alt>c")
set -euo pipefail

combinacao="${1:-Insert}"
script="$(cd "$(dirname "$0")" && pwd)/alternar-escuta.sh"
base="org.gnome.settings-daemon.plugins.media-keys"
caminho="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/clarisse/"
item="$base.custom-keybinding:$caminho"

atuais="$(gsettings get "$base" custom-keybindings)"
if [[ "$atuais" != *"$caminho"* ]]; then
  if [[ "$atuais" == "@as []" || "$atuais" == "[]" ]]; then
    novos="['$caminho']"
  else
    novos="${atuais%]}, '$caminho']"
  fi
  gsettings set "$base" custom-keybindings "$novos"
fi

gsettings set "$item" name "Clarisse: falar"
gsettings set "$item" command "$script"
gsettings set "$item" binding "$combinacao"

echo "Atalho cadastrado: $combinacao chama $script"
