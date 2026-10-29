#!/usr/bin/env python3
"""Preview do item selecionado na árvore (repotree.py), aberto pelo kitty como
overlay por cima do terminal. Ao fechar, o terminal aparece intacto.

Arquivos de texto com realce de sintaxe (pygments), pastas com o conteúdo,
imagens com o protocolo gráfico do kitty e binários só com o tamanho.
Uso (via repotree.py): preview.py <id-da-janela-do-terminal>
"""
import os
import signal
import subprocess
import sys
import time

from pygments import highlight
from pygments.formatters import Terminal256Formatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

OWNER = sys.argv[1]
STATE = os.path.join(os.environ.get("TMPDIR", "/tmp"), "sfpanel")
SEL = os.path.join(STATE, f"{OWNER}.sel")
KITTEN = "/Applications/kitty.app/Contents/MacOS/kitten"
IMAGES = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}
MAX_BYTES = 256 * 1024
FORMATTER = Terminal256Formatter(style="one-dark")


def fg(n):
    return f"\x1b[38;5;{n}m"


RESET, BOLD = "\x1b[0m", "\x1b[1m"
ANCHOR, DIR, FRAME, DIM = fg(39), fg(31), fg(242), fg(246)


def human(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}".replace(".", ",")
        size /= 1024


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def header(path, info):
    # caminho relativo à raiz do repo git; fora de um repo, com ~ no lugar da home
    root = os.path.dirname(path)
    while root != "/" and not os.path.exists(os.path.join(root, ".git")):
        root = os.path.dirname(root)
    home = os.path.expanduser("~")
    if root != "/":
        shown = os.path.join(os.path.basename(root), os.path.relpath(path, root))
    else:
        shown = "~" + path[len(home):] if path.startswith(home) else path
    return f" {ANCHOR}{BOLD}{shown}{RESET}  {FRAME}{info}{RESET}"


def body_dir(path, height):
    try:
        entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError as err:
        return f"não deu para abrir: {err.strerror}", [f" {DIM}{err.strerror}{RESET}"]
    rows = []
    for e in entries[:height]:
        if e.is_dir():
            rows.append(f" {DIR} {e.name}/{RESET}")
        else:
            rows.append(f" {DIM if e.name.startswith('.') else ''} {e.name}{RESET}")
    if len(entries) > height:
        rows[-1] = f" {FRAME}… +{len(entries) - height + 1}{RESET}"
    if not entries:
        rows = [f" {DIM}pasta vazia{RESET}"]
    return plural(len(entries), "item", "itens"), rows


def body_file(path, height):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        data = f.read(MAX_BYTES)
    if b"\0" in data[:8192]:
        return f"binário · {human(size)}", [f" {DIM}arquivo binário, sem preview{RESET}"]
    if not data.strip():
        return f"vazio · {human(size)}", [f" {DIM}arquivo vazio{RESET}"]
    text = data.decode("utf-8", "replace").expandtabs(4)
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    shown = lines[:height]
    try:
        lexer = get_lexer_for_filename(path, stripnl=False, stripall=False)
    except ClassNotFound:
        lexer = TextLexer()
    colored = highlight("\n".join(shown), lexer, FORMATTER).split("\n")[: len(shown)]
    width = len(str(len(shown)))
    rows = [f"{FRAME}{n:>{width + 1}} │{RESET} {line}" for n, line in enumerate(colored, 1)]
    more = "+" if size > MAX_BYTES else ""
    return f"{plural(len(lines), 'linha', 'linhas')}{more} · {human(size)}", rows


def draw(path, width, height):
    body_h = max(height - 2, 1)
    image = False
    if not path or not os.path.exists(path):
        info, rows = "", [f" {DIM}nada selecionado{RESET}"]
    elif os.path.isdir(path):
        info, rows = body_dir(path, body_h)
    elif path.rsplit(".", 1)[-1].lower() in IMAGES:
        info, rows, image = f"imagem · {human(os.path.getsize(path))}", [], True
    else:
        try:
            info, rows = body_file(path, body_h)
        except OSError as err:
            info, rows = "", [f" {DIM}{err.strerror}{RESET}"]
    out = [header(path or "", info), FRAME + "─" * width + RESET] + rows
    sys.stdout.write("\x1b[H" + "\r\n".join(r + RESET + "\x1b[K" for r in out[:height]) + "\x1b[J")
    sys.stdout.flush()
    subprocess.run([KITTEN, "icat", "--clear"], capture_output=False, stderr=subprocess.DEVNULL)
    if image:
        subprocess.run(
            [KITTEN, "icat", "--stdin=no", "--place", f"{width}x{body_h}@0x2", path],
            stderr=subprocess.DEVNULL,
        )


def main():
    sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[?7l")
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    last = None
    try:
        while True:
            try:
                stamp = os.stat(SEL).st_mtime_ns
            except OSError:
                stamp = None
            size = os.get_terminal_size()
            if (stamp, size) != last:
                last = (stamp, size)
                try:
                    with open(SEL) as f:
                        path = f.read().strip()
                except OSError:
                    path = ""
                draw(path, size.columns, size.lines)
            time.sleep(0.05)
    finally:
        sys.stdout.write("\x1b[?7h\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
