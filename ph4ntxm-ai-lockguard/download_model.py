# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)
MODEL_SHA256 = "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f"
DEFAULT_DEST = Path(__file__).resolve().with_name("face_detector.task")
MAX_MODEL_BYTES = 1024 * 1024


def verify_model(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_MODEL_BYTES:
        raise ValueError("Model missing or oversized; run download_model.py")
    if hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256:
        raise ValueError("Model checksum mismatch; run download_model.py --force")


def download_model(destination):
    destination = Path(destination)
    fd, temporary = tempfile.mkstemp(prefix=".lockguard-model-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            with urllib.request.urlopen(MODEL_URL, timeout=30) as response:
                size = 0
                while chunk := response.read(65536):
                    size += len(chunk)
                    if size > MAX_MODEL_BYTES:
                        raise ValueError("Model download exceeds size limit")
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        verify_model(temporary)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description="Download and verify the pinned face detector")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.dest.exists() and not args.force:
        verify_model(args.dest)
    else:
        download_model(args.dest)
    print("Face detector checksum verified.")


if __name__ == "__main__":
    main()
