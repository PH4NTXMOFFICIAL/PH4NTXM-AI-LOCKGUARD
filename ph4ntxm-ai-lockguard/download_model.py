#!/usr/bin/env python3
import argparse
import hashlib
import os
import urllib.request

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)

DEFAULT_DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_detector.task")


def download_with_progress(url: str, dest_path: str) -> None:
    tmp_path = dest_path + ".part"

    def _report(block_num: int, block_size: int, total_size: int) -> None:
        return

    try:
        urllib.request.urlretrieve(url, tmp_path, reporthook=_report)
    except Exception as exc:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise RuntimeError(f"Download failed from {url}: {exc}") from exc

    os.replace(tmp_path, dest_path)


def sha256sum(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download face_detector.task (blaze_face_short_range)")
    parser.add_argument("--dest", default=DEFAULT_DEST, help="Where to save the model file")
    parser.add_argument("--force", action="store_true", help="Download again even if the file already exists")
    args = parser.parse_args()

    if os.path.isfile(args.dest) and not args.force:
        return

    download_with_progress(MODEL_URL, args.dest)

    size_kb = os.path.getsize(args.dest) // 1024
    digest = sha256sum(args.dest)


if __name__ == "__main__":
    main()