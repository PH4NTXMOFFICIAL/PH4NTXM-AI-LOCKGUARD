# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

import os
import re
import subprocess
import time


class SessionError(RuntimeError):
    pass


def command(arguments):
    try:
        result = subprocess.run(
            ["/usr/bin/loginctl", *arguments], capture_output=True,
            text=True, timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SessionError("Session manager unavailable") from exc
    if result.returncode:
        raise SessionError("Session manager rejected the request")
    return result.stdout


def session_info(session):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session):
        raise SessionError("Invalid session identifier")
    text = command(["show-session", session, "--no-pager"])
    fields = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    if (fields.get("User") != str(os.getuid())
            or fields.get("Type") not in ("x11", "wayland")
            or fields.get("Class") != "user"
            or fields.get("Remote") != "no"):
        raise SessionError("Session is not this user's local graphical session")
    if fields.get("LockedHint") not in ("yes", "no"):
        raise SessionError("Session lock state is unavailable")
    return fields


def select_session(requested=None):
    if requested:
        fields = session_info(requested)
        if fields.get("Active") != "yes":
            raise SessionError("Requested session is not active")
        return requested, fields
    candidates = []
    for line in command(["list-sessions", "--no-legend", "--no-pager"]).splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[1] != str(os.getuid()):
            continue
        try:
            fields = session_info(parts[0])
        except SessionError:
            continue
        if fields.get("Active") == "yes":
            candidates.append((parts[0], fields))
    if len(candidates) != 1:
        raise SessionError("Expected exactly one active local graphical session; use --session when ambiguous")
    return candidates[0]


def locker_environment(fields, backend):
    if backend == "loginctl":
        return None
    if backend != "light-locker":
        raise SessionError("Unsupported lock backend")
    if not os.access("/usr/bin/light-locker-command", os.X_OK):
        raise SessionError("light-locker-command is not installed")
    display = fields.get("Display", "")
    if fields.get("Type") != "x11" or not re.fullmatch(r":[0-9]+(?:\.[0-9]+)?", display):
        raise SessionError("light-locker requires a local X11 display")
    current = os.environ.get("DISPLAY")
    if current and current.removesuffix(".0") != display.removesuffix(".0"):
        raise SessionError("The selected session differs from the current display")
    environment = os.environ.copy()
    environment["DISPLAY"] = display
    return environment


def request_lock(session, fields, backend):
    environment = locker_environment(fields, backend)
    if backend == "loginctl":
        command(["lock-session", session])
        return
    try:
        result = subprocess.run(
            ["/usr/bin/light-locker-command", "--lock"], capture_output=True,
            text=True, timeout=3, check=False, env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SessionError("light-locker request failed") from exc
    if result.returncode:
        raise SessionError("light-locker rejected the request")


def lock_session(session, stop, attempts=3, backend="loginctl"):
    for attempt in range(attempts):
        if stop.is_set():
            return False
        try:
            fields = session_info(session)
            if fields.get("Active") != "yes":
                return False
            if fields["LockedHint"] == "yes":
                return True
            request_lock(session, fields, backend)
            deadline = time.monotonic() + 15
            while not stop.is_set() and time.monotonic() < deadline:
                fields = session_info(session)
                if fields["LockedHint"] == "yes":
                    return True
                stop.wait(0.2)
        except SessionError:
            pass
        if attempt + 1 < attempts:
            stop.wait(1)
    return False
