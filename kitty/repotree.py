#!/usr/bin/env python3
"""Painel lateral do kitty: árvore do repositório atual, no estilo do p10k.

Mostra a hierarquia do repositório git em que o terminal está (fora de um
repo, a da pasta atual), respeitando o .gitignore. Expande o caminho até a
pasta atual e tudo mais que couber na altura do painel.

Com o foco (cmd+j, clique ou cmd+shift+e) entra no modo de navegação e
mostra o preview do item selecionado por cima do terminal (preview.py):
  w/s andam · a fecha a pasta/sobe · d abre/fecha a pasta
  enter: arquivo abre no nvim no terminal, pasta vira o cd do terminal
  esc ou j voltam ao terminal · e abre o superfile aqui · q fecha o painel
Uso (via sfpanel.sh): repotree.py <id-da-janela-do-terminal>
"""
import atexit
import os
import json
import select
import shlex
import signal
import subprocess
import sys
import termios
import time
import tty
from collections import deque

OWNER = sys.argv[1]
STATE = os.path.join(os.environ.get("TMPDIR", "/tmp"), "sfpanel")
SPF_DIR = os.path.expanduser("~/Library/Application Support/superfile")
HOME = os.path.expanduser("~")
SPF_WIDTH = 62  # mínimo exigido pelo superfile (a largura da árvore vem do sfpanel.sh)
RESCAN = 2.0  # segundos entre releituras do disco/git
SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", "target", "build", "dist"}
PREVIEW = os.path.expanduser("~/.config/kitty/preview.py")


def state(name):
    return os.path.join(STATE, f"{OWNER}.{name}")


def read_state(name, default=""):
    try:
        with open(state(name)) as f:
            return f.read().strip()
    except OSError:
        return default


# ── cores do ~/.p10k.zsh (xterm-256) e ícones (Nerd Font) ───────────────────

def fg(n):
    return f"\x1b[38;5;{n}m"


RESET, BOLD = "\x1b[0m", "\x1b[1m"
SELECTED = "\x1b[48;5;238m"  # fundo dos segmentos do p10k
DIR, ANCHOR, FRAME, DIM = fg(31), fg(39), fg(242), fg(246)
CLEAN, MODIFIED, DELETED = fg(76), fg(178), fg(160)
STATUS_COLOR = {"new": CLEAN, "mod": MODIFIED, "del": DELETED}

ICON_DIR, ICON_DIR_OPEN, ICON_FILE = "", "", ""
ICON_REPO, ICON_BRANCH = "", ""
ICONS = {
    "py": "", "js": "", "mjs": "", "ts": "", "tsx": "", "jsx": "",
    "java": "", "c": "", "h": "", "cpp": "", "hpp": "", "cc": "",
    "md": "", "json": "", "lua": "", "sh": "", "zsh": "",
    "go": "", "rs": "", "html": "", "css": "", "sql": "",
    "toml": "", "yml": "", "yaml": "", "lock": "", "txt": "",
}


def icon(name, is_dir, is_open):
    if is_dir:
        return ICON_DIR_OPEN if is_open else ICON_DIR
    if name.startswith(".git"):
        return ""
    return ICONS.get(name.rsplit(".", 1)[-1].lower() if "." in name else "", ICON_FILE)


# ── leitura do repositório ──────────────────────────────────────────────────

def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True).stdout.decode("utf-8", "replace")


def insert(tree, parts):
    node = tree
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = node[part] = {}
        node = child
    node.setdefault(parts[-1], None)


def scan_repo(root):
    tree = {}
    for path in git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0"):
        if path:
            insert(tree, path.split("/"))
    status = {}
    entries = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in "RC":
            i += 1  # caminho antigo do rename
        kind = "new" if "?" in code or "A" in code else "del" if "D" in code else "mod"
        parts = tuple(path.rstrip("/").split("/"))
        status[parts] = kind
        for n in range(1, len(parts)):
            status.setdefault(parts[:n], "mod")  # pasta com alterações dentro
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").strip() or "?"
    return tree, status, branch


def scan_dir(root, depth=3, limit=3000):
    tree, count = {}, 0
    queue = deque([(root, tree, 1)])
    while queue and count < limit:
        path, node, level = queue.popleft()
        try:
            entries = list(os.scandir(path))
        except OSError:
            continue
        for e in entries:
            if e.name.startswith(".") or count >= limit:
                continue
            count += 1
            if e.is_dir(follow_symlinks=False):
                node[e.name] = {}
                if level < depth and e.name not in SKIP:
                    queue.append((e.path, node[e.name], level + 1))
            else:
                node[e.name] = None
    return tree


def scan(cwd):
    root = git(cwd, "rev-parse", "--show-toplevel").strip()
    if root:
        tree, status, branch = scan_repo(root)
        return root, tree, status, branch
    return cwd, scan_dir(cwd), {}, None


# ── montagem das linhas ─────────────────────────────────────────────────────

def children(node):
    # pastas primeiro, depois arquivos, sem diferenciar maiúsculas
    return sorted(node.items(), key=lambda kv: (kv[1] is None, kv[0].lower()))


def choose_expanded(tree, cwd_parts, budget):
    """Abre o caminho até a pasta atual e, por nível, o que couber."""
    expanded = {()}
    for n in range(1, len(cwd_parts) + 1):
        expanded.add(tuple(cwd_parts[:n]))

    def node_at(path):
        node = tree
        for p in path:
            node = node.get(p) if isinstance(node, dict) else None
        return node if isinstance(node, dict) else None

    lines = sum(len(node_at(p) or {}) for p in expanded)
    queue = deque(sorted(
        (p + (name,) for p in expanded for name, child in children(node_at(p) or {})
         if isinstance(child, dict) and p + (name,) not in expanded),
        key=len,
    ))
    while queue:
        path = queue.popleft()
        node = node_at(path)
        if not node or path[-1] in SKIP or lines + len(node) > budget:
            continue
        expanded.add(path)
        lines += len(node)
        queue.extend(path + (n,) for n, c in children(node) if isinstance(c, dict))
    return expanded


def tree_lines(tree, status, cwd_parts, expanded, width):
    """Retorna [(texto, caminho, é_pasta, é_a_pasta_atual)]."""
    out = []
    cwd_t = tuple(cwd_parts)

    def walk(node, path, guides):
        items = children(node)
        for i, (name, child) in enumerate(items):
            last = i == len(items) - 1
            p = path + (name,)
            is_dir = isinstance(child, dict)
            is_open = p in expanded
            branch = FRAME + guides + ("└╴" if last else "├╴") + RESET
            used = len(guides) + 2 + 2
            color = STATUS_COLOR.get(status.get(p), "")
            extra = ""
            if is_dir:
                color = ANCHOR + (BOLD if p == cwd_t else "") if p == cwd_t[: len(p)] else color or DIR
                if not is_open and child:
                    extra = f" {len(child)}"
            if is_dir and p == cwd_t:
                extra += " ◂"
            room = max(width - used - len(extra), 1)
            label = name if len(name) <= room else name[: room - 1] + "…"
            text = f"{branch}{color}{icon(name, is_dir, is_open)} {label}{RESET}{FRAME}{extra}{RESET}"
            out.append((text, p, is_dir, p == cwd_t))
            if is_dir and is_open:
                walk(child, p, guides + ("  " if last else "│ "))

    walk(tree, (), "")
    return out


# ── tela ────────────────────────────────────────────────────────────────────

def kitten(*args, text=None):
    return subprocess.run(["kitten", "@", *args], input=text, capture_output=True, text=True)


def keys(data):
    """Separa a entrada em teclas: sequências de 3 bytes (setas, foco) ou 1 byte."""
    i = 0
    while i < len(data):
        if data[i:i + 1] == b"\x1b" and data[i + 1:i + 2] in (b"[", b"O") and i + 2 < len(data):
            yield data[i:i + 3]
            i += 3
        else:
            yield data[i:i + 1]
            i += 1


class Panel:
    def __init__(self):
        self.cwd = None
        self.root = None
        self.offset = 0
        self.last_scan = 0.0
        self.data = None
        self.frame = None
        self.lines = []
        self.nav = False  # modo de navegação (painel com foco)
        self.sel = None  # caminho selecionado, relativo à raiz
        self.opened, self.closed = set(), set()  # pastas abertas/fechadas à mão
        self.preview = None  # id da janela de preview
        self.tty_attrs = termios.tcgetattr(0)

    def enter(self):
        tty.setcbreak(0)
        # tela alternativa, sem cursor, sem quebra de linha, com aviso de foco
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[?1004h")
        sys.stdout.flush()
        self.frame = None

    def leave(self):
        termios.tcsetattr(0, termios.TCSADRAIN, self.tty_attrs)
        sys.stdout.write("\x1b[?1004l\x1b[?7h\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()

    def resize(self, target):
        cols = os.get_terminal_size().columns
        if cols != target:
            kitten("resize-window", "--self", "--axis=horizontal", f"--increment={target - cols}")

    # ── preview e foco ──

    def preview_open(self):
        if self.preview:
            return
        r = kitten("launch", "--type=overlay", f"--match=window_id:{OWNER}", f"--next-to=id:{OWNER}",
                   "--keep-focus", "--title=preview", f"--var=sfpreview={OWNER}",
                   sys.executable, PREVIEW, OWNER)
        self.preview = r.stdout.strip() or None
        if self.preview:  # cmd+j/cmd+e apertados no preview agem neste painel
            with open(os.path.join(STATE, f"panel-{self.preview}"), "w") as f:
                f.write(OWNER)

    def preview_close(self):
        if self.preview:
            kitten("close-window", f"--match=id:{self.preview}")
            for path in (os.path.join(STATE, f"panel-{self.preview}"), state("sel")):
                try:
                    os.remove(path)
                except OSError:
                    pass
            self.preview = None

    def set_nav(self, on):
        if on == self.nav:
            return
        self.nav = on
        if on:
            if self.sel is None or self.index(self.sel) is None:
                self.sel = self.cwd_parts()
            self.write_sel()
            self.preview_open()
        else:
            self.preview_close()

    def focused(self):
        r = kitten("ls", f"--match=id:{os.environ.get('KITTY_WINDOW_ID', '')}")
        try:
            return any(w["is_focused"] for o in json.loads(r.stdout) for t in o["tabs"] for w in t["windows"])
        except (ValueError, KeyError):
            return False

    def owner_at_prompt(self):
        r = kitten("ls", f"--match=id:{OWNER}")
        try:
            return any(w["at_prompt"] for o in json.loads(r.stdout) for t in o["tabs"] for w in t["windows"])
        except (ValueError, KeyError):
            return False

    def back(self):
        self.preview_close()
        kitten("focus-window", f"--match=id:{OWNER}")

    # ── dados ──

    def refresh(self, force=False):
        cwd = os.path.normpath(read_state("dir", self.cwd or HOME))
        if not os.path.isdir(cwd):
            cwd = self.cwd or HOME
        moved = cwd != self.cwd
        if moved or force or time.time() - self.last_scan >= RESCAN:
            self.cwd = cwd
            self.data = scan(cwd)
            self.last_scan = time.time()
            if self.data[0] != self.root:  # outro repo: esquece o que foi aberto à mão
                self.root = self.data[0]
                self.opened, self.closed, self.sel = set(), set(), None
        return moved

    def cwd_parts(self):
        rel = os.path.relpath(self.cwd, self.root)
        return () if rel == "." else tuple(rel.split(os.sep))

    def index(self, path):
        return next((i for i, line in enumerate(self.lines) if line[1] == path), None)

    def selected(self):
        i = self.index(self.sel)
        return self.lines[i] if i is not None else None

    def write_sel(self):
        if self.nav and self.sel is not None:
            with open(state("sel"), "w") as f:
                f.write(os.path.join(self.root, *self.sel))

    # ── desenho ──

    def layout(self):
        width, height = os.get_terminal_size()
        _, tree, status, _ = self.data
        cwd_parts = list(self.cwd_parts())
        view = max(height - 3, 1)
        expanded = (choose_expanded(tree, cwd_parts, view) | self.opened) - self.closed
        self.lines = tree_lines(tree, status, cwd_parts, expanded, width - 1)
        return view

    def draw(self, recenter):
        width, height = os.get_terminal_size()
        root, tree, status, branch = self.data
        view = self.layout()

        if self.nav:
            if self.index(self.sel) is None:  # selecionado sumiu: sobe até um pai visível
                while self.sel and self.index(self.sel) is None:
                    self.sel = self.sel[:-1]
                self.sel = self.sel if self.index(self.sel) is not None else (self.lines[0][1] if self.lines else None)
                self.write_sel()
            focus = self.index(self.sel) or 0
        else:
            focus = next((i for i, line in enumerate(self.lines) if line[3]), 0) if recenter else None
        if focus is not None and not self.offset <= focus < self.offset + view:
            self.offset = max(focus - view // 3, 0) if not self.nav or focus < self.offset else focus - view + 1
        self.offset = max(min(self.offset, len(self.lines) - view), 0)

        name = "~" if root == HOME else os.path.basename(root) or root
        head = f" {ANCHOR}{BOLD}{ICON_REPO if branch else ICON_DIR_OPEN} {name}{RESET}"
        if branch:
            head += f"  {MODIFIED if status else CLEAN}{ICON_BRANCH} {branch}{RESET}"
        up = "↑" if self.offset > 0 else " "
        down = "↓" if self.offset + view < len(self.lines) else " "
        hint = "⏎ abrir · a/d pasta · esc volta" if self.nav else "⌘j navegar"
        foot = f"{FRAME} {up}{down} {hint}"[: width + len(FRAME)] + RESET

        rows = [head + "\x1b[K", (ANCHOR if self.nav else FRAME) + "─" * width + RESET]
        for text, path, _, _ in self.lines[self.offset: self.offset + view]:
            if self.nav and path == self.sel:
                rows.append(SELECTED + " " + text.replace(RESET, RESET + SELECTED) + "\x1b[K" + RESET)
            else:
                rows.append(" " + text + "\x1b[K")
        rows += ["\x1b[K"] * (height - 1 - len(rows)) + [foot + "\x1b[K"]
        frame = "\x1b[H" + "\r\n".join(rows[:height])
        if frame != self.frame:
            sys.stdout.write(frame)
            sys.stdout.flush()
            self.frame = frame

    # ── ações ──

    def move(self, delta):
        if not self.lines:
            return
        i = self.index(self.sel)
        i = 0 if i is None else max(0, min(len(self.lines) - 1, i + delta))
        self.sel = self.lines[i][1]
        self.write_sel()

    def toggle_dir(self, path, is_open):
        if is_open:
            self.closed.add(path)
            self.opened.discard(path)
        else:
            self.opened.add(path)
            self.closed.discard(path)

    def is_open(self, path):
        i = self.index(path)
        return i is not None and i + 1 < len(self.lines) and self.lines[i + 1][1][:-1] == path

    def left(self):
        line = self.selected()
        if line and line[2] and self.is_open(line[1]):
            self.toggle_dir(line[1], True)
        elif self.sel and len(self.sel) > 1:
            self.sel = self.sel[:-1]
            self.write_sel()

    def right(self):
        line = self.selected()
        if line and line[2]:
            self.toggle_dir(line[1], self.is_open(line[1]))

    def activate(self):
        line = self.selected()
        if not line:
            return
        path = os.path.join(self.root, *line[1])
        if self.owner_at_prompt():
            # ctrl+u limpa o que estiver digitado; o comando roda no terminal
            cmd = ("cd " if line[2] else "nvim ") + shlex.quote(os.path.relpath(path, self.cwd))
            kitten("send-text", f"--match=id:{OWNER}", "--stdin", text="\x15" + cmd + "\r")
            self.back()
        elif not line[2]:  # terminal ocupado: abre numa aba nova
            subprocess.run([os.path.expanduser("~/.config/kitty/sfpanel-open"), path])
        else:
            self.right()

    def superfile(self):
        nav = self.nav
        self.set_nav(False)
        self.leave()
        width = os.get_terminal_size().columns
        self.resize(SPF_WIDTH)
        env = dict(os.environ, XDG_DATA_HOME=os.path.join(SPF_DIR, "panel"))
        while True:
            try:
                os.remove(state("restart"))
            except OSError:
                pass
            # o hook do zsh encerra o superfile a cada cd e marca "restart"
            subprocess.call(["spf", "-c", os.path.join(SPF_DIR, "panel.toml"), read_state("dir", self.cwd)], env=env)
            if not os.path.exists(state("restart")):
                break
        self.resize(width)
        self.enter()
        self.refresh(force=True)
        self.layout()
        self.set_nav(nav)

    def handle(self, key):
        """Trata uma tecla; devolve False para fechar o painel."""
        view = max(os.get_terminal_size().lines - 3, 1)
        if key == b"\x1b[I":
            self.set_nav(True)
        elif key == b"\x1b[O":
            self.set_nav(False)
        elif key in (b"q", b"Q"):
            if self.data and self.data[3]:  # dentro de um repo: não reabrir sozinho nele
                with open(state("dismissed"), "w") as f:
                    f.write(self.data[0])
            return False
        elif not self.nav:
            return True
        elif key in (b"w", b"\x1b[A", b"\x1bOA"):
            self.move(-1)
        elif key in (b"s", b"\x1b[B", b"\x1bOB"):
            self.move(1)
        elif key == b"W":
            self.move(-(view // 2))
        elif key == b"S":
            self.move(view // 2)
        elif key in (b"a", b"\x1b[D", b"\x1bOD"):
            self.left()
        elif key in (b"d", b"\x1b[C", b"\x1bOC"):
            self.right()
        elif key in (b"\r", b"\n"):
            self.activate()
        elif key in (b"\x1b", b"j"):
            self.back()
        elif key == b"e":
            self.superfile()
        return True

    def run(self):
        self.enter()
        self.refresh(force=True)
        self.layout()
        if self.focused():  # aberto pelo cmd+j: o foco chegou antes do aviso de foco
            self.set_nav(True)
        self.draw(recenter=True)
        while True:
            ready, _, _ = select.select([0], [], [], 0.25)
            data = os.read(0, 64) if ready else b""
            for key in keys(data):
                if not self.handle(key):
                    return
            moved = self.refresh()
            self.draw(recenter=moved)


def cleanup(panel):
    panel.preview_close()
    paths = [state(name) for name in ("pid", "win", "auto", "sel")]
    paths.append(os.path.join(STATE, "panel-" + os.environ.get("KITTY_WINDOW_ID", "")))
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass
    try:
        panel.leave()
    except OSError:  # janela já fechada pelo kitty
        pass


if __name__ == "__main__":
    os.makedirs(STATE, exist_ok=True)
    with open(state("pid"), "w") as f:
        f.write(str(os.getpid()))
    panel = Panel()
    atexit.register(cleanup, panel)
    for sig in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(sig, lambda *_: sys.exit(0))
    try:
        panel.run()
    except KeyboardInterrupt:
        pass
