# Painel lateral do kitty: árvore do repositório (~/.config/kitty/repotree.py).
# Abre sozinho ao entrar num repo git e fecha ao sair; cmd+e (ou `painel`)
# abre/fecha à mão. Carregado no topo do ~/.zshrc, antes do prompt
# instantâneo do p10k: o painel abre antes do primeiro prompt ser desenhado,
# então nenhuma linha quebra quando o terminal estreita.
[[ -n $KITTY_WINDOW_ID && -o interactive && -z $NVIM ]] || return 0

typeset -g _painel_st=${TMPDIR:-/tmp}/sfpanel
typeset -g _painel_sh=~/.config/kitty/sfpanel.sh
[[ -d $_painel_st ]] || mkdir -p $_painel_st

# raiz do repo git de $PWD em REPLY, sem chamar o git (é instantâneo)
_painel_root() {
  local d=$PWD
  while [[ -n $d && ! -e $d/.git ]]; do d=${d%/*}; done
  REPLY=${d:+${d:A}}
}

# a largura do terminal mudou depois de já ter coisa na tela: o kitty
# reembrulhou as linhas antigas; manda a tela para o histórico de rolagem
# (nada se perde) e o próximo prompt sai limpo no topo
_painel_clear() { print -n '\e[22J\e[H' }

# $1 = "cd" quando chamado por uma troca de pasta
_painel_sync() {
  local st=$_painel_st id=$KITTY_WINDOW_ID was=0 now=0
  print -r -- $PWD > $st/$id.dir
  if [[ -r $st/$id.pid ]]; then
    # superfile aberto no painel: reabre na pasta nova
    : > $st/$id.restart
    pkill -TERM -P "$(<$st/$id.pid)" spf 2>/dev/null
  fi
  [[ -e $st/$id.win ]] && was=1
  _painel_root
  if [[ -n $REPLY ]]; then
    if (( ! was && COLUMNS >= 84 )) && [[ ! -r $st/$id.dismissed || $(<$st/$id.dismissed) != $REPLY ]]; then
      sh $_painel_sh open $id $COLUMNS 2>/dev/null && : > $st/$id.auto
    fi
  else
    rm -f $st/$id.dismissed  # saiu de todo repo: o "não reabrir" expira
    [[ -e $st/$id.auto ]] && sh $_painel_sh close $id 2>/dev/null
  fi
  [[ -e $st/$id.win ]] && now=1
  [[ $1 == cd && $was != $now ]] && _painel_clear
}

_painel_cd() { _painel_sync cd }

_painel_close() {
  [[ -e $_painel_st/$KITTY_WINDOW_ID.win ]] && sh $_painel_sh close $KITTY_WINDOW_ID
  rm -f $_painel_st/$KITTY_WINDOW_ID.*(N)
}

painel() {
  local win=$_painel_st/$KITTY_WINDOW_ID.win was=0 now=0
  [[ -e $win ]] && was=1
  sh $_painel_sh toggle $KITTY_WINDOW_ID $COLUMNS
  [[ -e $win ]] && now=1
  (( was != now )) && _painel_clear
}

# superfile em tela cheia: com a árvore aberta, o terminal ocupa a janela
# toda (layout stack do kitty) enquanto o comando roda e a árvore volta depois
painel_zoom() {
  [[ -e $_painel_st/$KITTY_WINDOW_ID.win ]] || { "$@"; return }
  kitten @ goto-layout --match "window_id:$KITTY_WINDOW_ID" stack 2>/dev/null
  "$@"
  local ret=$?
  kitten @ goto-layout --match "window_id:$KITTY_WINDOW_ID" splits 2>/dev/null
  return $ret
}

autoload -Uz add-zsh-hook
add-zsh-hook chpwd _painel_cd
add-zsh-hook zshexit _painel_close
_painel_sync
