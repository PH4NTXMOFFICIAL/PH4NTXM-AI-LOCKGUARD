# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

import os
import time

from download_model import verify_model
from network_guard import restrict_worker_network


def camera_worker(connection, settings, model):
    cap = None
    detector = None
    try:
        restrict_worker_network()
        verify_model(model)
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["OPENBLAS_NUM_THREADS"] = "1"
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        cv2.setNumThreads(1)
        options = vision.FaceDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.VIDEO,
            min_detection_confidence=settings.confidence,
        )
        detector = vision.FaceDetector.create_from_options(options)
        cap = cv2.VideoCapture(settings.camera_index, cv2.CAP_V4L2)
        if not cap.isOpened():
            raise RuntimeError("Camera unavailable")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.height)
        cap.set(cv2.CAP_PROP_FPS, settings.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        previous_timestamp = -1
        while True:
            start = time.monotonic()
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError("Camera frame unavailable")
            height, width = frame.shape[:2]
            scale = min(settings.width / width, settings.height / height, 1)
            frame = cv2.resize(frame, (max(1, int(width * scale)), max(1, int(height * scale))))
            image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
            )
            timestamp = max(previous_timestamp + 1, int(start * 1000))
            result = detector.detect_for_video(image, timestamp)
            previous_timestamp = timestamp
            connection.send((start, len(result.detections or [])))
            time.sleep(max(0, 1 / settings.fps - (time.monotonic() - start)))
    except Exception:
        try:
            connection.send((time.monotonic(), None))
        except (BrokenPipeError, OSError):
            pass
    finally:
        if cap is not None:
            cap.release()
        if detector is not None:
            detector.close()
        connection.close()
