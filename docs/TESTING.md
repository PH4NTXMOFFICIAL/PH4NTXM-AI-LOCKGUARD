# [ VALIDATION ]

Run `python3 tests/test-lockguard.py` and `python3 tests/test-installer.py` from the repository root. The installer tests simulate APT, virtual-environment creation and systemd, covering missing packages, partial environments, updates and failure handling. These tests simulate camera and session behavior; they do not use your camera or lock your desktop. Coverage includes session ownership, lock confirmation, bounded retries, missing/frozen camera input, pause/resume, model integrity, and IPv4/IPv6 socket rejection.

A separate smoke test used MediaPipe 1.0.1 and the pinned model on 30 black 320×240 frames with the worker's network filter enabled. All returned zero faces; the process reached approximately 143 MiB peak RSS. This is a synthetic compatibility measurement, not a real-camera resource budget or detection-accuracy test.

Before relying on protection, test on the target desktop:

- `./panic.sh` visibly locks the correct session and requires authentication.
- One visible face reaches Armed; leaving the frame triggers the absence timeout.
- A second visible face triggers locking after the configured consecutive frames.
- Disconnecting the camera requests locking with the default failure policy.
- Pause and an already locked session release the camera; resume/unlock restarts detection.
- Check startup after login and verify that failed locking is reported rather than treated as success.

Lighting, camera compatibility, actual screen-lock behavior and resource use still require these live checks. Neither unit tests nor `LockedHint` alone establish production readiness.
