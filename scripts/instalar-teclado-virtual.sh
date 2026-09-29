#!/usr/bin/env bash
# Instala o teclado virtual da Clarisse (ydotool) e o wl-clipboard, que ela usa para colar texto.
#
# O pacote sugere pôr o usuário no grupo "input", mas esse grupo também lê tudo o que é
# digitado no teclado de verdade. Aqui a liberação é só do /dev/uinput (o teclado virtual)
# e só para quem está usando a máquina (TAG uaccess), sem grupo e sem sair da sessão.
set -euo pipefail

echo "1/4 Instalando o ydotool e o wl-clipboard (vai pedir a sua senha)..."
sudo apt-get install -y ydotool wl-clipboard

echo "2/4 Liberando só o teclado virtual para quem está na máquina..."
echo 'KERNEL=="uinput", TAG+="uaccess", OPTIONS+="static_node=uinput"' \
  | sudo tee /etc/udev/rules.d/70-clarisse-uinput.rules >/dev/null
sudo udevadm control --reload-rules
sudo udevadm trigger --action=add --name-match=uinput

echo "3/4 Ligando o serviço do teclado virtual..."
systemctl --user daemon-reload
systemctl --user enable --now ydotool.service

echo "4/4 Conferindo..."
sleep 1
if [[ -w /dev/uinput ]] && systemctl --user is-active --quiet ydotool.service; then
  echo "Teclado virtual pronto."
else
  echo "Algo não ficou certo: /dev/uinput gravável? $([[ -w /dev/uinput ]] && echo sim || echo não)." >&2
  echo "Serviço: $(systemctl --user is-active ydotool.service)." >&2
  exit 1
fi
