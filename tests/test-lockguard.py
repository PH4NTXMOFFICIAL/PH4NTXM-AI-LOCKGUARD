# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "ph4ntxm-ai-lockguard"
sys.path.insert(0, str(SOURCE))

import download_model
import ph4ntxm_lockguard as guard
import session_lock
from guard_policy import FacePolicy, Settings


class PolicyTests(unittest.TestCase):
    def test_absence_and_recovery(self):
        policy = FacePolicy(Settings())
        self.assertIsNone(policy.observe(0, 10))
        self.assertIsNone(policy.observe(0, 14.9))
        self.assertEqual(policy.observe(0, 15), "no_face")
        self.assertIsNone(policy.observe(1, 16))
        self.assertIsNone(policy.observe(0, 17))

    def test_multiple_faces_must_be_consecutive(self):
        policy = FacePolicy(Settings())
        for count in [2, 2, 1, 2, 0, 2, 2]:
            self.assertIsNone(policy.observe(count, 10))
        self.assertEqual(policy.observe(2, 11), "multiple_faces")

    def test_invalid_config(self):
        for values in ({"fps": 0}, {"fps": float("nan")}, {"width": 10000},
                       {"multiple_face_frames": 1.5}, {"lock_on_camera_loss": "false"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Settings(**values).validate()

    def test_unknown_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text("unknown = 1\n")
            with self.assertRaises(ValueError):
                guard.load_settings(path)


class SessionTests(unittest.TestCase):
    def fields(self, **updates):
        fields = {"User": str(os.getuid()), "Type": "x11", "Class": "user",
                  "Active": "yes", "Remote": "no", "LockedHint": "no"}
        fields.update(updates)
        return fields

    def test_unfiltered_session_query(self):
        fields = self.fields(Display=":0", CanLock="yes")
        output = "\n".join(f"{key}={value}" for key, value in fields.items())
        def response(arguments):
            return "" if any(arg.startswith("--property=") for arg in arguments) else output
        with patch.object(session_lock, "command", side_effect=response):
            self.assertEqual(session_lock.session_info("2"), fields)

    def test_rejects_other_users_remote_and_non_graphical(self):
        for values in ({"User": "999999"}, {"Remote": "yes"}, {"Type": "tty"},
                       {"Class": "greeter"}, {"LockedHint": ""}):
            output = "\n".join(f"{key}={value}" for key, value in self.fields(**values).items())
            with patch.object(session_lock, "command", return_value=output):
                with self.assertRaises(session_lock.SessionError):
                    session_lock.session_info("c4")

    def test_selects_current_user_only(self):
        listing = f"2 999999 other seat0\nc4 {os.getuid()} operator seat0\n"
        with patch.object(session_lock, "command", return_value=listing), patch.object(
                session_lock, "session_info", return_value=self.fields()) as info:
            self.assertEqual(session_lock.select_session()[0], "c4")
            info.assert_called_once_with("c4")

    def test_ambiguous_sessions_fail(self):
        listing = f"c4 {os.getuid()} operator seat0\nc7 {os.getuid()} operator seat1\n"
        with patch.object(session_lock, "command", return_value=listing), patch.object(
                session_lock, "session_info", return_value=self.fields()):
            with self.assertRaises(session_lock.SessionError):
                session_lock.select_session()

    def test_inactive_explicit_session_fails(self):
        with patch.object(session_lock, "session_info", return_value=self.fields(Active="no")):
            with self.assertRaises(session_lock.SessionError):
                session_lock.select_session("c4")

    def test_acknowledgement_is_not_success(self):
        with patch.object(session_lock, "session_info", return_value=self.fields()), patch.object(
                session_lock, "command", return_value="") as command, patch.object(
                session_lock.time, "monotonic", side_effect=[0, 16]), patch.object(
                threading.Event, "wait", return_value=False):
            self.assertFalse(session_lock.lock_session("c4", threading.Event(), attempts=1))
            command.assert_called_once_with(["lock-session", "c4"])

    def test_lock_is_confirmed(self):
        with patch.object(session_lock, "session_info", side_effect=[self.fields(), self.fields(LockedHint="yes")]), patch.object(
                session_lock, "command", return_value=""):
            self.assertTrue(session_lock.lock_session("c4", threading.Event()))

    def test_lock_errors_retry_with_a_limit(self):
        with patch.object(session_lock, "session_info", return_value=self.fields()), patch.object(
                session_lock, "command", side_effect=session_lock.SessionError("failed")) as command, patch.object(
                threading.Event, "wait", return_value=False):
            self.assertFalse(session_lock.lock_session("c4", threading.Event()))
            self.assertEqual(command.call_count, 3)

    def test_light_locker_uses_native_command(self):
        fields = self.fields(Display=":0")
        with patch.object(session_lock, "session_info", side_effect=[fields, self.fields(LockedHint="yes", Active="no")]), patch.object(
                session_lock.os, "access", return_value=True), patch.dict(os.environ, {"DISPLAY": ":0"}), patch.object(
                session_lock.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, patch.object(
                session_lock, "command") as loginctl:
            self.assertTrue(session_lock.lock_session("2", threading.Event(), backend="light-locker"))
            self.assertEqual(run.call_args.args[0], ["/usr/bin/light-locker-command", "--lock"])
            loginctl.assert_not_called()

    def test_light_locker_failure_never_falls_back_to_loginctl(self):
        with patch.object(session_lock, "session_info", return_value=self.fields(Display=":0")), patch.object(
                session_lock.os, "access", return_value=True), patch.dict(os.environ, {"DISPLAY": ":0"}), patch.object(
                session_lock.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)), patch.object(
                session_lock, "command") as loginctl:
            self.assertFalse(session_lock.lock_session("2", threading.Event(), attempts=1, backend="light-locker"))
            loginctl.assert_not_called()

    def test_greeter_switch_can_precede_lock_hint(self):
        with patch.object(session_lock, "session_info", side_effect=[self.fields(), self.fields(Active="no"), self.fields(Active="no", LockedHint="yes")]), patch.object(
                session_lock, "command"), patch.object(threading.Event, "wait", return_value=False):
            self.assertTrue(session_lock.lock_session("2", threading.Event()))

    def test_light_locker_rejects_different_display(self):
        with patch.object(session_lock.os, "access", return_value=True), patch.dict(os.environ, {"DISPLAY": ":1"}):
            with self.assertRaises(session_lock.SessionError):
                session_lock.locker_environment(self.fields(Display=":0"), "light-locker")

    def test_light_locker_requires_helper(self):
        with patch.object(session_lock.os, "access", return_value=False):
            with self.assertRaises(session_lock.SessionError):
                session_lock.locker_environment(self.fields(Display=":0"), "light-locker")

    def test_stop_cancels_lock(self):
        stop = threading.Event()
        stop.set()
        with patch.object(session_lock, "command") as command:
            self.assertFalse(session_lock.lock_session("c4", stop))
            command.assert_not_called()


class ModelTests(unittest.TestCase):
    def test_existing_tampered_model_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model"
            path.write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                download_model.verify_model(path)

    def test_failed_download_keeps_existing_model(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model"
            path.write_bytes(b"original")
            with patch.object(download_model.urllib.request, "urlopen", return_value=io.BytesIO(b"bad")):
                with self.assertRaises(ValueError):
                    download_model.download_model(path)
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_verified_download_is_atomic(self):
        data = b"verified model"
        with tempfile.TemporaryDirectory() as directory, patch.object(
                download_model, "MODEL_SHA256", hashlib.sha256(data).hexdigest()), patch.object(
                download_model.urllib.request, "urlopen", return_value=io.BytesIO(data)):
            path = Path(directory) / "model"
            download_model.download_model(path)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class RuntimeTests(unittest.TestCase):
    def simulate(self, frames, settings=None, end=12, pause_at=None, resume_at=None, lock_ok=True):
        clock = [100.0]
        handlers = {}
        states = []
        workers = []
        locks = []
        fields = {"LockedHint": "no"}
        class Event:
            stopped = False
            def is_set(self):
                return self.stopped or clock[0] >= 100 + end
            def set(self):
                self.stopped = True
            def wait(self, seconds):
                clock[0] += seconds
                for when, sig in ((pause_at, guard.signal.SIGUSR1), (resume_at, guard.signal.SIGUSR2)):
                    if when is not None and clock[0] - seconds < 100 + when <= clock[0]:
                        handlers[sig](sig, None)
        class Process:
            def is_alive(self):
                return True
        class Worker:
            def __init__(self, *_):
                self.process = None
                self.started = 0
            def start(self):
                self.process = Process()
                self.started = clock[0]
                workers.append(("start", clock[0]))
            def stop(self):
                if self.process is not None:
                    workers.append(("stop", clock[0]))
                self.process = None
            def poll(self):
                if self.process is None:
                    return []
                value = frames(clock[0] - 100)
                return [] if value == "hang" else [(clock[0], value)]
        class Status:
            def __init__(self, *_):
                pass
            def publish(self, value):
                states.append(value)
        def lock(*_, **kwargs):
            locks.append(clock[0])
            if lock_ok:
                fields["LockedHint"] = "yes"
            return lock_ok
        with tempfile.TemporaryDirectory() as directory, patch.object(guard.time, "monotonic", side_effect=lambda: clock[0]), patch.object(
                guard.threading, "Event", Event), patch.object(guard.signal, "signal", side_effect=lambda sig, fn: handlers.update({sig: fn})), patch.object(
                guard, "Worker", Worker), patch.object(guard, "Status", Status), patch.object(
                guard, "select_session", return_value=("c4", fields)), patch.object(guard, "lock_session", side_effect=lock):
            guard.run_guard(settings or Settings(startup_timeout=5), Path("unused"), None, Path(directory))
        return states, workers, locks

    def test_frozen_camera_locks_after_deadline(self):
        states, workers, locks = self.simulate(lambda t: 1 if t < 1 else "hang")
        self.assertEqual(len(locks), 1)
        self.assertIn("Armed", states)
        self.assertIn("Locked", states)
        self.assertTrue(105 <= locks[0] <= 107)
        self.assertEqual(workers[-1][0], "stop")

    def test_camera_never_opens(self):
        states, _, locks = self.simulate(lambda _: None)
        self.assertEqual(len(locks), 1)
        self.assertNotIn("Armed", states)

    def test_camera_loss_can_be_report_only_and_recover(self):
        states, _, locks = self.simulate(lambda t: "hang" if t < 7 else 1,
                                        Settings(startup_timeout=5, lock_on_camera_loss=False), end=15)
        self.assertFalse(locks)
        self.assertIn("Camera unavailable", states)
        self.assertIn("Armed", states)

    def test_pause_releases_camera_and_resume_rearms(self):
        states, workers, locks = self.simulate(lambda _: 1, pause_at=2, resume_at=5)
        self.assertFalse(locks)
        self.assertIn("Paused", states)
        self.assertEqual([action for action, _ in workers], ["start", "stop", "start", "stop"])

    def test_failed_lock_is_retried_without_success(self):
        states, _, locks = self.simulate(lambda _: 2, lock_ok=False)
        self.assertGreaterEqual(len(locks), 2)
        self.assertIn("Lock failed", states)
        self.assertNotIn("Locked", states)

    def test_private_status(self):
        with tempfile.TemporaryDirectory() as directory:
            status = guard.Status(Path(directory))
            status.publish("Armed")
            self.assertEqual(status.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(set(json.loads(status.path.read_text())), {"state", "updated"})

    def test_worker_filter_blocks_ip_sockets(self):
        code = """
import socket
from network_guard import restrict_worker_network
restrict_worker_network()
for family in (socket.AF_INET, socket.AF_INET6):
    try:
        sock = socket.socket(family, socket.SOCK_STREAM)
    except PermissionError:
        continue
    else:
        sock.close()
        raise SystemExit(1)
socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close()
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=SOURCE, timeout=10)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
