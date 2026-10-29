# Barra do kitty no estilo "classic" do Powerlevel10k (~/.p10k.zsh):
# abas à esquerda terminando em ▓▒░ e, à direita, começando em ░▒▓,
# o uso de cpu, ram, gpu e disco, atualizado a cada INTERVAL segundos.
import ctypes
import os
import sys

from ctypes import POINTER, byref, c_char_p, c_int, c_int64, c_size_t, c_uint32, c_uint64, c_void_p

from kitty.fast_data_types import Screen, add_timer, get_boss
from kitty.tab_bar import DrawData, ExtraData, TabBarData, as_rgb
from kitty.utils import color_as_int

INTERVAL = 2.0

# cores do ~/.p10k.zsh (paleta xterm-256)
BG = as_rgb(0x444444)        # 238 POWERLEVEL9K_BACKGROUND
SEP = as_rgb(0x949494)       # 246 separador │
DIM = as_rgb(0x6c6c6c)       # 242 moldura
ACTIVE = as_rgb(0x00afff)    # 39  DIR_ANCHOR
INACTIVE = as_rgb(0x8787af)  # 103 DIR_SHORTENED
NORMAL = as_rgb(0x5f8787)    # 66  RAM / LOAD / TIME
WARN = as_rgb(0xd7af00)      # 178 LOAD_WARNING
CRIT = as_rgb(0xd75f00)      # 166 LOAD_CRITICAL

# (rótulo, alerta, crítico) em %
METRICS = (("cpu", 60, 85), ("ram", 85, 95), ("gpu", 70, 90), ("disk", 90, 95))


# ── leitura das métricas (macOS, sem sudo) ──────────────────────────────────
# Tudo via APIs do sistema (Mach/IOKit): criar subprocessos de dentro do
# kitty trava a thread de coleta.

_libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
_libc.mach_host_self.restype = c_uint32
_libc.host_statistics.argtypes = [c_uint32, c_int, c_void_p, POINTER(c_uint32)]
_libc.host_statistics64.argtypes = [c_uint32, c_int, c_void_p, POINTER(c_uint32)]
_libc.sysctlbyname.argtypes = [c_char_p, c_void_p, POINTER(c_size_t), c_void_p, c_size_t]
_host = _libc.mach_host_self()
_cpu_prev = None


def cpu_percent():
    global _cpu_prev
    ticks = (c_uint32 * 4)()  # user, system, idle, nice
    count = c_uint32(4)
    if _libc.host_statistics(_host, 3, ticks, byref(count)) != 0:  # HOST_CPU_LOAD_INFO
        return None
    prev, _cpu_prev = _cpu_prev, list(ticks)
    if prev is None:
        return None
    user, system, idle, nice = ((now - old) % 2**32 for now, old in zip(ticks, prev))
    total = user + system + idle + nice
    return 100 * (total - idle) / total if total else None


class _VMStats64(ctypes.Structure):  # <mach/vm_statistics.h>
    _fields_ = (
        [(n, c_uint32) for n in ("free_count", "active_count", "inactive_count", "wire_count")]
        + [(n, c_uint64) for n in ("zero_fill_count", "reactivations", "pageins", "pageouts",
                                   "faults", "cow_faults", "lookups", "hits", "purges")]
        + [(n, c_uint32) for n in ("purgeable_count", "speculative_count")]
        + [(n, c_uint64) for n in ("decompressions", "compressions", "swapins", "swapouts")]
        + [(n, c_uint32) for n in ("compressor_page_count", "throttled_count",
                                   "external_page_count", "internal_page_count")]
        + [("total_uncompressed_pages_in_compressor", c_uint64), ("swapped_count", c_uint64)]
    )


def _sysctl_u64(name):
    value, size = c_uint64(), c_size_t(8)
    _libc.sysctlbyname(name, byref(value), byref(size), None, 0)
    return value.value


_page = os.sysconf("SC_PAGESIZE")
_ram_total = _sysctl_u64(b"hw.memsize")


def ram_percent():
    # mesma conta do Monitor de Atividade: memória de apps + wired + comprimida
    vm = _VMStats64()
    count = c_uint32(ctypes.sizeof(vm) // 4)
    if _libc.host_statistics64(_host, 4, byref(vm), byref(count)) != 0:  # HOST_VM_INFO64
        return None
    used = vm.internal_page_count - vm.purgeable_count + vm.wire_count + vm.compressor_page_count
    return 100 * used * _page / _ram_total


_iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
_cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
_iokit.IOServiceMatching.restype = c_void_p
_iokit.IOServiceMatching.argtypes = [c_char_p]
_iokit.IOServiceGetMatchingServices.argtypes = [c_uint32, c_void_p, POINTER(c_uint32)]
_iokit.IOIteratorNext.restype = c_uint32
_iokit.IOIteratorNext.argtypes = [c_uint32]
_iokit.IORegistryEntryCreateCFProperty.restype = c_void_p
_iokit.IORegistryEntryCreateCFProperty.argtypes = [c_uint32, c_void_p, c_void_p, c_uint32]
_iokit.IOObjectRelease.argtypes = [c_uint32]
_cf.CFStringCreateWithCString.restype = c_void_p
_cf.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint32]
_cf.CFDictionaryGetValue.restype = c_void_p
_cf.CFDictionaryGetValue.argtypes = [c_void_p, c_void_p]
_cf.CFNumberGetValue.argtypes = [c_void_p, c_int, c_void_p]
_cf.CFRelease.argtypes = [c_void_p]
_K_PERF = _cf.CFStringCreateWithCString(None, b"PerformanceStatistics", 0x08000100)
_K_UTIL = _cf.CFStringCreateWithCString(None, b"Device Utilization %", 0x08000100)


def gpu_percent():
    # o mesmo "Device Utilization %" que `ioreg -c IOAccelerator` mostra
    it = c_uint32()
    if _iokit.IOServiceGetMatchingServices(0, _iokit.IOServiceMatching(b"IOAccelerator"), byref(it)):
        return None
    value = None
    while svc := _iokit.IOIteratorNext(it):
        perf = _iokit.IORegistryEntryCreateCFProperty(svc, _K_PERF, None, 0)
        if perf:
            num = _cf.CFDictionaryGetValue(perf, _K_UTIL)
            v = c_int64()
            if num and _cf.CFNumberGetValue(num, 4, byref(v)):  # kCFNumberSInt64Type
                value = v.value
            _cf.CFRelease(perf)
        _iokit.IOObjectRelease(svc)
    _iokit.IOObjectRelease(it)
    return value


def disk_percent():
    st = os.statvfs("/")
    return 100 * (1 - st.f_bavail / st.f_blocks)


READERS = {"cpu": cpu_percent, "ram": ram_percent, "gpu": gpu_percent, "disk": disk_percent}


# ── coleta + redesenho periódico ────────────────────────────────────────────
# Roda no timer do kitty, na thread principal: o kitty não libera o GIL
# enquanto espera eventos, então uma thread separada ficaria parada.
# As leituras acima são chamadas de sistema rápidas (~1 ms no total).
# O estado fica num módulo à parte para não duplicar o timer se o kitty
# recarregar este arquivo.

_shared = sys.modules.setdefault("_kitty_statusbar_v3", type(sys)("_kitty_statusbar_v3"))
if not hasattr(_shared, "values"):
    _shared.values = {}
    _shared.started = False


def _collect():
    for key, read in READERS.items():
        try:
            _shared.values[key] = read()
        except Exception:
            _shared.values[key] = None


def _tick(timer_id):
    _collect()
    for tm in get_boss().all_tab_managers:
        tm.mark_tab_bar_dirty()


def _start():
    if _shared.started:
        return
    _shared.started = True
    _collect()
    add_timer(_tick, INTERVAL, True)


# ── desenho ─────────────────────────────────────────────────────────────────

def _put(screen, text, fg, bg=BG, bold=False):
    screen.cursor.fg, screen.cursor.bg, screen.cursor.bold = fg, bg, bold
    screen.draw(text)


def _status_cells():
    cells = []
    for i, (label, warn, crit) in enumerate(METRICS):
        value = _shared.values.get(label)
        if value is None:
            text, color = "--", NORMAL
        else:
            text = f"{value:2.0f}%"
            color = CRIT if value >= crit else WARN if value >= warn else NORMAL
        if i:
            cells.append((" │", SEP))
        cells.append((f" {label} ", SEP))
        cells.append((text, color))
    cells.append((" ", SEP))
    return cells


def _draw_status(screen, default_bg):
    cells = _status_cells()
    width = 3 + sum(len(text) for text, _ in cells)
    x = screen.columns - width
    if x <= screen.cursor.x:  # sem espaço: mostra só as abas
        return
    screen.cursor.x = x
    _put(screen, "░▒▓", BG, default_bg)
    for text, color in cells:
        _put(screen, text, color)


def draw_tab(
    draw_data: DrawData, screen: Screen, tab: TabBarData,
    before: int, max_tab_length: int, index: int, is_last: bool,
    extra_data: ExtraData,
) -> int:
    _start()
    default_bg = as_rgb(color_as_int(draw_data.default_bg))
    if index > 1:
        _put(screen, "│", SEP)
    title = tab.title
    room = max(max_tab_length - len(str(index)) - 3, 1)
    if len(title) > room:
        title = title[: room - 1] + "…"
    _put(screen, f" {index} ", ACTIVE if tab.is_active else DIM, bold=tab.is_active)
    _put(screen, f"{title} ", ACTIVE if tab.is_active else INACTIVE, bold=tab.is_active)
    end = screen.cursor.x
    if is_last:
        _put(screen, "▓▒░", BG, default_bg)
        end = screen.cursor.x
        _draw_status(screen, default_bg)
    return end
