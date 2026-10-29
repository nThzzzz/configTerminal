# configTerminal

Minha configuração de terminal no macOS: **kitty + zsh (oh-my-zsh/powerlevel10k) + Neovim (LazyVim) + superfile**, com movimentação **WASD** em tudo, uma barra de status discreta e uma árvore do repositório sempre à esquerda.

## O que tem aqui

- **Barra de status no rodapé do kitty**, no mesmo estilo do powerlevel10k: abas à esquerda e uso de **cpu, ram, gpu e disco** à direita, atualizados a cada 2s (amarelo/laranja quando passa do limite).
- **Árvore do repositório à esquerda**: abre sozinha ao entrar num repositório git e fecha ao sair. Respeita o `.gitignore`, destaca a pasta atual (`◂`) e mostra o status do git (amarelo = modificado, verde = novo).
- **Navegação pela árvore com preview**: `cmd+j` leva o foco para a árvore e mostra, por cima do terminal, o preview do item selecionado (código com realce de sintaxe, pastas e imagens).
- **WASD** no Neovim, no superfile e no explorer do LazyVim.
- **`sf`** abre o superfile em tela cheia; ao sair, a árvore volta e o terminal faz `cd` para a pasta onde você parou.

## Atalhos

### kitty

| Atalho | Faz |
|---|---|
| `cmd+j` | vai para a árvore navegar (e volta) |
| `cmd+e` | abre/fecha a árvore em qualquer pasta |
| `cmd+shift+e` | alterna o foco entre a árvore e o terminal |

### Árvore (com foco)

| Tecla | Faz |
|---|---|
| `w` / `s` | sobe / desce (`W` / `S` pulam meia tela) |
| `a` | fecha a pasta ou sobe para a pasta pai |
| `d` | abre/fecha a pasta |
| `Enter` | arquivo: abre no nvim no terminal · pasta: o terminal faz `cd` |
| `Esc`, `j` | volta ao terminal |
| `e` | abre o superfile ali mesmo |
| `q` | fecha a árvore (não reabre sozinha nesse repo até você sair dele) |

### Neovim (WASD)

| Tecla | Faz |
|---|---|
| `w` `a` `s` `d` | ↑ ← ↓ → |
| `k` | apagar (*kill*): `kk` apaga a linha, `kiw` apaga a palavra |
| `j` | pulo rápido (*jump*, flash) |
| `l` | próxima palavra |
| `h` | append e text object "around" (`vhp`, `khw`, `ch"`) |
| `<espaço>uW` | liga/desliga o modo WASD (a escolha fica salva) |

Maiúsculas (`W`, `A`, `S`, `D`, `K`...) continuam com a função original.

### superfile

| Tecla | Faz |
|---|---|
| `w` / `s` | sobe / desce |
| `a` | pasta pai |
| `d` | abre |
| `k` | fecha o painel de arquivos |
| `j` | vai para a sidebar |
| `W` / `S` | seleção para cima / baixo (modo seleção) |

## Requisitos

- macOS
- [kitty](https://sw.kovidgoyal.net/kitty/) com a fonte **JetBrainsMono Nerd Font**
- [oh-my-zsh](https://ohmyz.sh/) com [powerlevel10k](https://github.com/romkatv/powerlevel10k) e os plugins `zsh-syntax-highlighting` e `zsh-autosuggestions`
- [Neovim](https://neovim.io/) (o LazyVim se instala sozinho na primeira abertura)
- [superfile](https://superfile.dev/) (`spf`)
- Python 3 com [pygments](https://pygments.org/) para o preview: `pip3 install pygments`

## Instalação

```sh
git clone https://github.com/nThzzzz/configTerminal
cd configTerminal
sh install.sh
```

O script copia cada arquivo para o lugar certo e faz backup do que já existia em `~/.config/backup-configTerminal-<data>`. Depois é só fechar o kitty (`cmd+q`) e abrir de novo.

## Estrutura

```
kitty/      kitty.conf, barra de status (tab_bar.py), árvore (repotree.py),
            preview (preview.py) e os scripts que abrem/fecham o painel
zsh/        .zshrc e .p10k.zsh
nvim/       config do LazyVim com o modo WASD (lua/config/wasd.lua)
superfile/  config, atalhos WASD e a config compacta usada no painel
```
