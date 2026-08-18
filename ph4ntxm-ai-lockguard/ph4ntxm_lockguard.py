#!/usr/bin/env python3
import argparse
import logging
import logging.handlers
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_detector.task")
DEFAULT_PANIC_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panic.sh")
DEFAULT_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ph4ntxm_lockguard.log")

FRAME_WIDTH = 320
FRAME_HEIGHT = 240
SAMPLE_FPS = 5
OWNER_MISSING_TIMEOUT = 5.0
PANIC_COOLDOWN = 15.0
MIN_DETECTION_CONFIDENCE = 0.5
CAMERA_OPEN_RETRY_DELAY = 5.0

logger = logging.getLogger("ph4ntxm_lockguard")


def setup_logging(log_path: str, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=2 * 1024 * 1024, backupCount=2
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError as exc:
        sys.stderr.write(f"[ph4ntxm_lockguard] Could not open log file '{log_path}': {exc}\n")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)


@dataclass
class GuardState:
    running: bool = True
    no_face_since: float = None
    last_panic_ts: float = 0.0


def trigger_panic(panic_script_path: str, reason: str, state: GuardState) -> None:
    now = time.monotonic()
    if now - state.last_panic_ts < PANIC_COOLDOWN:
        logger.debug("Panic is already in cooldown, ignoring new trigger (%s)", reason)
        return

    if not os.path.isfile(panic_script_path):
        logger.error("Panic script not found: %s", panic_script_path)
        return

    logger.warning("PANIC TRIGGERED (%s) -> executing %s", reason, panic_script_path)
    state.last_panic_ts = now

    try:
        subprocess.Popen(
            ["/bin/bash", panic_script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception as exc:
        logger.error("Failed to execute panic script: %s", exc)


def open_camera(camera_index: int) -> cv2.VideoCapture:
    while True:
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            logger.info("Camera (index=%d) opened successfully at %dx%d", camera_index, FRAME_WIDTH, FRAME_HEIGHT)
            return cap

        logger.warning(
            "Could not open camera (index=%d). Retrying in %.0fs...",
            camera_index, CAMERA_OPEN_RETRY_DELAY,
        )
        cap.release()
        time.sleep(CAMERA_OPEN_RETRY_DELAY)


def build_face_detector(model_path: str) -> mp_vision.FaceDetector:
    if not os.path.isfile(model_path):
        logger.error("Model '%s' not found. Run download_model.py first.", model_path)
        sys.exit(1)

    base_options = mp_python.BaseOptions(model_asset_path=model_path)
    options = mp_vision.FaceDetectorOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.VIDEO,
        min_detection_confidence=MIN_DETECTION_CONFIDENCE,
    )
    return mp_vision.FaceDetector.create_from_options(options)


def main() -> None:
    parser = argparse.ArgumentParser(description="PH4NTXM AI LockGuard - headless anti shoulder-surfing daemon")
    parser.add_argument("--model", default=DEFAULT_MODEL_PATH, help="Path to face_detector.task")
    parser.add_argument("--panic-script", default=DEFAULT_PANIC_SCRIPT, help="Path to panic.sh")
    parser.add_argument("--camera-index", type=int, default=0, help="Camera index (/dev/videoN)")
    parser.add_argument("--log-file", default=DEFAULT_LOG_PATH, help="Path for the log file")
    parser.add_argument("--owner-missing-timeout", type=float, default=OWNER_MISSING_TIMEOUT,
                         help="Seconds without a detected face before triggering")
    parser.add_argument("--verbose", action="store_true", help="Detailed (debug) logging")
    args = parser.parse_args()

    setup_logging(args.log_file, args.verbose)

    state = GuardState()

    def handle_signal(signum, _frame):
        logger.info("Received signal %d, shutting down...", signum)
        state.running = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    detector = build_face_detector(args.model)
    cap = open_camera(args.camera_index)

    frame_interval = 1.0 / SAMPLE_FPS
    start_time = time.monotonic()

    try:
        while state.running:
            loop_start = time.monotonic()

            ok, frame = cap.read()
            if not ok or frame is None:
                logger.warning("Failed to read frame, reconnecting camera...")
                cap.release()
                cap = open_camera(args.camera_index)
                continue

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            timestamp_ms = int((time.monotonic() - start_time) * 1000)
            result = detector.detect_for_video(mp_image, timestamp_ms)

            face_count = len(result.detections) if result and result.detections else 0

            if face_count > 1:
                logger.info("Detected %d faces simultaneously.", face_count)
                state.no_face_since = None
                trigger_panic(args.panic_script, "shoulder_surfing", state)

            elif face_count == 0:
                if state.no_face_since is None:
                    state.no_face_since = time.monotonic()
                elapsed = time.monotonic() - state.no_face_since
                if elapsed > args.owner_missing_timeout:
                    logger.info("No face detected for %.1fs.", elapsed)
                    trigger_panic(args.panic_script, "owner_missing", state)

            else:
                state.no_face_since = None

            elapsed_loop = time.monotonic() - loop_start
            sleep_time = frame_interval - elapsed_loop
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        logger.info("Cleaning up resources (camera/detector)...")
        cap.release()
        detector.close()


if __name__ == "__main__":
    main()