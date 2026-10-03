"""Verify who is on the other end of a Unix domain socket (macOS).

A loopback TCP port is not an access-control boundary: every local process can
connect to 127.0.0.1. A Unix socket is not one either by itself — but macOS lets
the server ask the kernel *which process* is connected, so agent access can be
tied to an identified local program instead of a bearer token sitting in a file
that any same-user process can copy.

This raises the bar substantially (no on-disk credential to steal, and every
client is named before it is granted anything). It is **not** a hard boundary
against malware already running as the same user: such code can exec our own
interpreter and pass the same checks. See docs/07-local-agent-access.md.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import socket
import struct
from dataclasses import dataclass
from pathlib import Path

SOL_LOCAL = 0
LOCAL_PEERCRED = 0x001
LOCAL_PEERPID = 0x002

_libc = ctypes.CDLL(ctypes.util.find_library("c") or "/usr/lib/libc.dylib", use_errno=True)
try:
    _libproc = ctypes.CDLL(ctypes.util.find_library("proc") or "/usr/lib/libproc.dylib", use_errno=True)
except OSError:  # pragma: no cover - only on non-macOS
    _libproc = None


@dataclass(frozen=True)
class Peer:
    """The local process on the other end of a connection."""

    uid: int
    pid: int | None
    executable: str
    command: tuple[str, ...] = ()

    @property
    def command_line(self) -> str:
        return " ".join(self.command) if self.command else self.executable

    @property
    def is_owner(self) -> bool:
        return self.uid == os.getuid()


def peer_pid(sock: socket.socket) -> int | None:
    value = ctypes.c_int(0)
    size = ctypes.c_int(ctypes.sizeof(value))
    if _libc.getsockopt(sock.fileno(), SOL_LOCAL, LOCAL_PEERPID, ctypes.byref(value), ctypes.byref(size)) != 0:
        return None
    return int(value.value) or None


def peer_uid(sock: socket.socket) -> int | None:
    # struct xucred { u_int cr_version; uid_t cr_uid; short cr_ngroups; gid_t cr_groups[16]; }
    buffer = ctypes.create_string_buffer(80)
    size = ctypes.c_int(ctypes.sizeof(buffer))
    if _libc.getsockopt(sock.fileno(), SOL_LOCAL, LOCAL_PEERCRED, buffer, ctypes.byref(size)) != 0:
        return None
    _version, uid = struct.unpack_from("=II", buffer.raw, 0)
    return int(uid)


def executable_path(pid: int | None) -> str:
    """Resolve a pid to its executable path ("" when unknown/not permitted)."""
    if _libproc is None or not pid:
        return ""
    buffer = ctypes.create_string_buffer(4096)
    written = _libproc.proc_pidpath(ctypes.c_int(pid), buffer, ctypes.c_int(len(buffer)))
    if written <= 0:
        return ""
    return buffer.value.decode("utf-8", "replace")


CTL_KERN = 1
KERN_PROCARGS2 = 49
_ARGV_MAX = 1024 * 64


def command_line(pid: int | None) -> list[str]:
    """The peer's argv (macOS KERN_PROCARGS2). Empty when unavailable.

    This is what separates our MCP server (`python -m backend.mcp_server`) from an
    arbitrary Python script: `proc_pidpath` only names the interpreter.
    """
    if not pid:
        return []
    mib = (ctypes.c_int * 3)(CTL_KERN, KERN_PROCARGS2, pid)
    buffer = ctypes.create_string_buffer(_ARGV_MAX)
    size = ctypes.c_size_t(_ARGV_MAX)
    if _libc.sysctl(mib, 3, buffer, ctypes.byref(size), None, 0) != 0:
        return []
    raw = buffer.raw[: size.value]
    if len(raw) < 4:
        return []
    argc = int.from_bytes(raw[:4], "little")
    parts = raw[4:].split(b"\x00")
    # 布局：argc | exec path | 若干填充 \0 | argv[0..argc-1]
    return [p.decode("utf-8", "replace") for p in parts[1:] if p][:argc]


def identify(sock: socket.socket) -> Peer:
    """Identify the peer of a connected Unix domain socket."""
    uid = peer_uid(sock)
    pid = peer_pid(sock)
    return Peer(uid=os.getuid() if uid is None else uid, pid=pid, executable=executable_path(pid),
                command=tuple(command_line(pid)))


def describe(path: str) -> str:
    """A short, human-recognisable name for an executable path."""
    if not path:
        return "未知程序"
    name = Path(path).name
    for marker, label in (
        (".app/Contents/MacOS/", None),      # /Applications/X.app/Contents/MacOS/X → X.app
        ("Electron", None),
    ):
        if marker in path:
            head = path.split(marker)[0]
            if head.endswith(".app"):
                return Path(head).name
    return name
