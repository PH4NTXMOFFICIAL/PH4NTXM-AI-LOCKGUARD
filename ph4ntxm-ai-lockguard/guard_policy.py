# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

import math
from dataclasses import dataclass


@dataclass
class Settings:
    lock_backend: str = "light-locker"
    camera_index: int = 0
    width: int = 320
    height: int = 240
    fps: float = 5.0
    confidence: float = 0.5
    absence_timeout: float = 5.0
    multiple_face_frames: int = 3
    camera_timeout: float = 5.0
    startup_timeout: float = 20.0
    lock_on_camera_loss: bool = True

    def validate(self):
        if self.lock_backend not in ("light-locker", "loginctl"):
            raise ValueError("lock_backend must be light-locker or loginctl")
        limits = {
            "camera_index": (0, 64), "width": (160, 1280),
            "height": (120, 720), "fps": (1, 15),
            "confidence": (0.1, 1), "absence_timeout": (1, 300),
            "multiple_face_frames": (1, 30), "camera_timeout": (2, 60),
            "startup_timeout": (5, 120),
        }
        integers = {"camera_index", "width", "height", "multiple_face_frames"}
        for name, (low, high) in limits.items():
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Invalid setting: " + name)
            if not low <= value <= high or (name in integers and type(value) is not int):
                raise ValueError("Out-of-range setting: " + name)
        if type(self.lock_on_camera_loss) is not bool:
            raise ValueError("lock_on_camera_loss must be boolean")
        return self


class FacePolicy:
    def __init__(self, settings):
        self.settings = settings
        self.reset()

    def reset(self):
        self.absent_since = None
        self.multiple_frames = 0

    def observe(self, count, now):
        if count > 1:
            self.absent_since = None
            self.multiple_frames += 1
            if self.multiple_frames >= self.settings.multiple_face_frames:
                return "multiple_faces"
        elif count == 0:
            self.multiple_frames = 0
            if self.absent_since is None:
                self.absent_since = now
            if now - self.absent_since >= self.settings.absence_timeout:
                return "no_face"
        else:
            self.reset()
        return None
