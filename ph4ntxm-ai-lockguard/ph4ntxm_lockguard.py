#!/usr/bin/env python3
# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

import argparse
import fcntl
import json
import logging
import multiprocessing
import os
from pathlib import Path
import signal
import stat
import tempfile
import threading
import time
import tomllib

from camera_worker import camera_worker
from download_model import verify_model
from guard_policy import FacePolicy, Settings
from session_lock import SessionError, lock_session, locker_environment, select_session

BASE = Path(__file__).resolve().parent
logger = logging.getLogger("ph4ntxm_lockguard")


def runtime_directory():
    base = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    info = base.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("A private user runtime directory is required")
    directory = base / "ph4ntxm-lockguard"
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("Unsafe runtime directory")
    return directory


class Status:
    def __init__(self, directory):
        self.path = directory / "status.json"
        self.previous = None
        self.last_write = 0

    def publish(self, state):
        now = time.monotonic()
        if state == self.previous and now - self.last_write < 1:
            return
        if state != self.previous:
            logger.info("State: %s", state)
        fd, name = tempfile.mkstemp(prefix=".status-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump({"state": state, "updated": now}, handle)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        self.previous = state
        self.last_write = now


def read_status(directory):
    try:
        value = json.loads((directory / "status.json").read_text())
        age = time.monotonic() - value["updated"]
        print(value["state"] if 0 <= age < 30 else "Stopped / stale status")
    except (OSError, ValueError, KeyError, TypeError):
        print("Stopped / no status")


class Worker:
    def __init__(self, settings, model):
        self.settings = settings
        self.model = model
        self.process = None
        self.connection = None
        self.started = 0

    def start(self):
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        self.connection = receiver
        self.process = context.Process(
            target=camera_worker, args=(sender, self.settings, self.model), daemon=True,
        )
        try:
            self.process.start()
            self.started = time.monotonic()
        except Exception:
            receiver.close()
            self.connection = None
            self.process = None
            raise
        finally:
            sender.close()

    def stop(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=1)
            self.process.close()
            self.process = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def poll(self):
        if self.connection is None:
            return []
        events = []
        try:
            for _ in range(32):
                if not self.connection.poll():
                    break
                events.append(self.connection.recv())
        except (EOFError, OSError):
            pass
        return events


def load_settings(path):
    data = tomllib.loads(path.read_text())
    if set(data) - set(Settings.__dataclass_fields__):
        raise ValueError("Unknown configuration option")
    return Settings(**data).validate()


def run_guard(settings, model, requested_session, directory, paused=False):
    stop = threading.Event()
    controls = {"paused": paused}
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGUSR1, lambda *_: controls.update(paused=True))
    signal.signal(signal.SIGUSR2, lambda *_: controls.update(paused=False))
    descriptor = os.open(directory / "guard.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(descriptor)
        raise RuntimeError("LockGuard is already running")
    status = Status(directory)
    worker = Worker(settings, model)
    policy = FacePolicy(settings)
    session = None
    session_checked = -float("inf")
    fields = None
    started = time.monotonic()
    last_frame = None
    last_event = -float("inf")
    retry_after = 0
    pending = None
    last_attempt = -float("inf")
    try:
        while not stop.is_set():
            now = time.monotonic()
            if controls["paused"]:
                worker.stop()
                policy.reset()
                session = None
                pending = None
                session_checked = -float("inf")
                status.publish("Paused")
                stop.wait(0.2)
                continue
            if now - session_checked >= 1:
                try:
                    selected, fields = select_session(requested_session)
                    if selected != session:
                        worker.stop()
                        policy.reset()
                        session = selected
                        started = now
                        last_frame = None
                        last_event = -float("inf")
                        retry_after = now
                        pending = None
                except SessionError:
                    worker.stop()
                    session = None
                    pending = None
                    fields = None
                session_checked = time.monotonic()
            if session is None:
                status.publish("Waiting for graphical session")
                stop.wait(0.2)
                continue
            if fields["LockedHint"] == "yes":
                worker.stop()
                policy.reset()
                last_frame = None
                last_event = -float("inf")
                started = now
                pending = None
                status.publish("Locked")
                stop.wait(0.2)
                continue
            if worker.process is None and now >= retry_after:
                worker.start()
            for timestamp, count in worker.poll():
                now = time.monotonic()
                if count is None:
                    worker.stop()
                    policy.reset()
                    retry_after = now + 3
                    break
                if timestamp <= last_event or not 0 <= now - timestamp < settings.camera_timeout:
                    continue
                last_event = timestamp
                last_frame = timestamp
                reason = policy.observe(count, timestamp)
                if reason:
                    pending = reason
            now = time.monotonic()
            timeout = settings.startup_timeout if last_frame is None else settings.camera_timeout
            unavailable = now - (last_frame if last_frame is not None else started) >= timeout
            if unavailable:
                policy.reset()
                worker_timeout = (settings.camera_timeout if last_frame is not None
                                  and last_frame >= worker.started else settings.startup_timeout)
                worker_reference = (last_frame if last_frame is not None
                                    and last_frame >= worker.started else worker.started)
                if worker.process is not None and now - worker_reference >= worker_timeout:
                    worker.stop()
                    retry_after = now + 3
                if settings.lock_on_camera_loss:
                    pending = pending or "camera_unavailable"
            if worker.process is not None and not worker.process.is_alive():
                worker.stop()
                policy.reset()
                retry_after = now + 3
            if pending and now - last_attempt >= 5:
                status.publish("Lock requested")
                if lock_session(session, stop, backend=settings.lock_backend):
                    worker.stop()
                    fields["LockedHint"] = "yes"
                    policy.reset()
                    last_frame = None
                    last_event = -float("inf")
                    started = time.monotonic()
                    pending = None
                    status.publish("Locked")
                else:
                    status.publish("Lock failed")
                last_attempt = time.monotonic()
                session_checked = -float("inf")
            elif pending:
                status.publish("Lock failed")
            elif unavailable:
                status.publish("Camera unavailable")
            elif worker.process is None:
                status.publish("Camera unavailable")
            elif last_frame is None or last_frame < worker.started:
                status.publish("Starting camera")
            else:
                status.publish("Armed")
            stop.wait(0.2)
    finally:
        worker.stop()
        status.publish("Stopped")
        os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description="PH4NTXM AI LockGuard")
    parser.add_argument("--config", type=Path, default=BASE / "lockguard.toml")
    parser.add_argument("--model", type=Path, default=BASE / "face_detector.task")
    parser.add_argument("--session", help="Explicit local graphical session identifier")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--status", action="store_true")
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--test-lock", action="store_true")
    parser.add_argument("--paused", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if os.getuid() == 0:
        parser.exit(1, "Run LockGuard as the graphical-session user, not root.\n")
    try:
        if args.status:
            read_status(runtime_directory())
            return
        settings = load_settings(args.config)
        if args.test_lock:
            session, _ = select_session(args.session)
            if not lock_session(session, threading.Event(), backend=settings.lock_backend):
                raise RuntimeError("Session lock was not confirmed by logind")
            print("Session lock reported by logind; verify the lock screen before enabling protection.")
            return
        verify_model(args.model)
        if args.check:
            _, fields = select_session(args.session)
            locker_environment(fields, settings.lock_backend)
            print("Configuration, model checksum and graphical-session properties passed. Camera and screen locker still require a live test.")
            return
        run_guard(settings, args.model, args.session, runtime_directory(), args.paused)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        parser.exit(1, f"LockGuard: {exc}\n")


if __name__ == "__main__":
    main()
