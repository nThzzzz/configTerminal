#!/bin/sh
# Instala as configs deste repositório nos lugares certos (macOS).
# O que já existir é copiado antes para ~/.config/backup-configTerminal-<data>.
set -e
cd "$(dirname "$0")"

SPF="$HOME/Library/Application Support/superfile"
BACKUP="$HOME/.config/backup-configTerminal-$(date +%Y%m%d-%H%M%S)"

put() {  # put <origem> <destino>
  if [ -e "$2" ]; then
    mkdir -p "$BACKUP"
    cp -R "$2" "$BACKUP/"
    rm -rf "$2"
  fi
  mkdir -p "$(dirname "$2")"
  cp -R "$1" "$2"
  echo "  $2"
}

echo "Instalando:"
put zsh/.zshrc "$HOME/.zshrc"
put zsh/.p10k.zsh "$HOME/.p10k.zsh"
put nvim "$HOME/.config/nvim"
for f in kitty/*; do put "$f" "$HOME/.config/kitty/$(basename "$f")"; done
for f in superfile/*; do put "$f" "$SPF/$(basename "$f")"; done

# os atalhos do kitty e o editor do painel usam caminhos absolutos
sed -i '' "s|/Users/zanvetor|$HOME|g" "$HOME/.config/kitty/kitty.conf" "$SPF/panel.toml"
chmod +x "$HOME/.config/kitty/sfpanel.sh" "$HOME/.config/kitty/sfpanel-open"

if [ -d "$BACKUP" ]; then
  echo "Backup do que existia: $BACKUP"
fi
echo "Pronto. Feche o kitty (cmd+q) e abra de novo."
