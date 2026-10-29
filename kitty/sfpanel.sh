#!/bin/sh
# Painel lateral do kitty: árvore do repositório (repotree.py) + superfile.
#   sfpanel.sh open <id> [colunas]     abre à esquerda do terminal <id>
#   sfpanel.sh close <id>              fecha
#   sfpanel.sh toggle <id> [colunas]   abre/fecha à mão (cmd+e ou `painel`)
#   sfpanel.sh jump <id>               cmd+j: leva o foco do terminal para a
#                                      árvore (abrindo-a se preciso) e de volta
#   sfpanel.sh run <id>                (interno) roda dentro do painel
# Abrir/fechar sozinho ao entrar/sair de um repo fica em painel.zsh.
# Estado em $STATE/<id>.*: dir (pasta do terminal), win (janela do painel),
# pid (processo do painel), auto (aberto sozinho), dismissed (repo em que
# você fechou o painel; não reabre sozinho nele até você sair).

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/Applications/kitty.app/Contents/MacOS:$PATH"
# o cmd+e roda este script com --allow-remote-control (KITTY_LISTEN_ON=fd:N)
[ -z "$KITTY_LISTEN_ON" ] && [ -n "$KITTY_PID" ] && export KITTY_LISTEN_ON="unix:/tmp/kitty-$KITTY_PID"

STATE="${TMPDIR:-/tmp}/sfpanel"
SPF_DIR="$HOME/Library/Application Support/superfile"
WIDTH=34
mkdir -p "$STATE"

lock() {
  n=0
  until mkdir "$STATE/$1.lock" 2>/dev/null; do
    n=$((n + 1))
    [ $n -ge 40 ] && break  # lock esquecido: segue em frente
    sleep 0.05
  done
  trap "rmdir '$STATE/$1.lock' 2>/dev/null" EXIT
}

# "colunas parado-no-prompt focado" do terminal $1, ex.: "148 1 1"
window_info() {
  kitten @ ls --match "id:$1" 2>/dev/null | python3 -I -c '
import json, sys
w = [w for o in json.load(sys.stdin) for t in o["tabs"] for w in t["windows"]][0]
print(w["columns"], int(w["at_prompt"]), int(w["is_focused"]))'
}

open_panel() {  # $1 = id do terminal, $2 = largura atual dele
  # o bias é a fatia da janela nova (o painel): ele já nasce com WIDTH
  # colunas, sem redimensionar depois (o que embaralharia o prompt)
  bias=$(LC_ALL=C awk -v c="${2:-0}" -v w="$WIDTH" 'BEGIN { printf "%.2f", (c > w ? (w + 0.5) * 100 / c : 50) }')
  win=$(kitten @ launch --type=window --match "window_id:$1" --next-to "id:$1" \
    --location=before --bias="$bias" --keep-focus --cwd="$(cat "$STATE/$1.dir")" \
    --var "sfpanel=$1" --title "árvore" /bin/sh "$0" run "$1") || return 1
  echo "$win" > "$STATE/$1.win"
  echo "$1" > "$STATE/panel-$win"
}

close_panel() {
  # fecha o painel e o preview deste terminal (inclusive algum órfão)
  kitten @ close-window --match "var:sfpanel=^$1\$ or var:sfpreview=^$1\$" 2>/dev/null
  [ -f "$STATE/$1.win" ] && rm -f "$STATE/panel-$(cat "$STATE/$1.win")"
  rm -f "$STATE/$1.win" "$STATE/$1.auto" "$STATE/$1.pid"
}

open_manual() {  # aberto à mão: vale em qualquer pasta e cancela o "não reabrir"
  [ -f "$STATE/$1.dir" ] || pwd > "$STATE/$1.dir"
  rm -f "$STATE/$1.dismissed"
  open_panel "$1" "$2"
}

# com o terminal parado no prompt, o kitty reembrulhou as linhas antigas na
# nova largura; manda tudo acima do prompt para o histórico ($2 = window_info)
clear_above_prompt() {
  case "$2" in
  *" 1 1") kitten @ action --match "id:$1" clear_terminal to_cursor_scroll active ;;
  esac
}

case "$1" in
open)
  lock "$2"
  [ -f "$STATE/$2.win" ] && exit 0
  open_panel "$2" "${3:-$(window_info "$2" | cut -d' ' -f1)}"
  ;;

close)
  lock "$2"
  close_panel "$2"
  ;;

toggle)
  id=$2
  # atalho apertado com o foco no próprio painel: age no terminal dono dele
  [ -f "$STATE/panel-$id" ] && id=$(cat "$STATE/panel-$id")
  lock "$id"
  info=$(window_info "$id")
  if [ -f "$STATE/$id.win" ]; then
    root=$(git -C "$(cat "$STATE/$id.dir" 2>/dev/null || pwd)" rev-parse --show-toplevel 2>/dev/null)
    [ -n "$root" ] && echo "$root" > "$STATE/$id.dismissed"
    close_panel "$id"
  else
    open_manual "$id" "${3:-${info%% *}}"
  fi
  clear_above_prompt "$id" "$info"
  ;;

jump)
  id=$2
  if [ -f "$STATE/panel-$id" ]; then
    # foco na árvore (ou no preview): volta ao terminal
    kitten @ focus-window --match "id:$(cat "$STATE/panel-$id")"
    exit
  fi
  lock "$id"
  if [ ! -f "$STATE/$id.win" ]; then
    info=$(window_info "$id")
    open_manual "$id" "${info%% *}" || exit 1
    clear_above_prompt "$id" "$info"
  fi
  # a árvore entra no modo de navegação ao receber o foco
  kitten @ focus-window --match "id:$(cat "$STATE/$id.win")"
  ;;

run)
  # estado próprio do superfile no painel (rodapé, ocultos); fixados compartilhados
  mkdir -p "$SPF_DIR/panel/superfile"
  cd "$SPF_DIR/panel/superfile" || exit
  [ -e firstUseCheck ] || : > firstUseCheck
  [ -e toggleFooter ] || printf false > toggleFooter
  [ -e pinned.json ] || ln -s "$SPF_DIR/pinned.json" pinned.json
  exec python3 "$HOME/.config/kitty/repotree.py" "$2"
  ;;
esac
