# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

import ctypes
import ctypes.util
import errno
import platform
import socket


class Comparison(ctypes.Structure):
    _fields_ = [
        ("arg", ctypes.c_uint), ("op", ctypes.c_int),
        ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64),
    ]


def restrict_worker_network():
    if platform.machine() not in ("x86_64", "aarch64"):
        raise RuntimeError("Network restriction requires Linux x86_64 or aarch64")
    library = ctypes.util.find_library("seccomp")
    if not library:
        raise RuntimeError("libseccomp is required")
    lib = ctypes.CDLL(library)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
        ctypes.c_uint, ctypes.POINTER(Comparison),
    ]
    lib.seccomp_rule_add_array.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    context = lib.seccomp_init(0x7fff0000)
    if not context:
        raise RuntimeError("Cannot initialize network restriction")
    try:
        syscall = lib.seccomp_syscall_resolve_name(b"socket")
        comparison = Comparison(0, 1, socket.AF_UNIX, 0)
        if syscall < 0 or lib.seccomp_rule_add_array(
            context, 0x00050000 | errno.EPERM, syscall, 1,
            ctypes.byref(comparison),
        ) < 0 or lib.seccomp_load(context) < 0:
            raise RuntimeError("Cannot enforce network restriction")
    finally:
        lib.seccomp_release(context)
