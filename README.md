# [ PH4NTXM AI LOCKGUARD ]

Local camera-assisted locking for Linux graphical sessions. LockGuard counts visible faces; it does not recognize the owner or authenticate anyone. A single unfamiliar face can satisfy the presence check, and people outside the camera view cannot be detected.

## [ DETECTION ]

The defaults use 320×240 frames at 5 FPS. Five seconds without a detected face, or three consecutive frames containing multiple faces, request a session lock. Camera or inference failure also requests a lock after a bounded timeout; this behavior is configurable.

## [ SESSION PROTECTION ]

LockGuard selects one active, local graphical session belonging to the current user. Ambiguous sessions require an explicit selection. The default lock backend invokes `light-locker-command --lock`; `loginctl` is an explicit alternative for other compatible desktops. Both check logind's `LockedHint` and retry on failure, without automatically switching backends. A compatible screen locker must already be installed and tested: logind reporting a lock is not an independent verification of the lock screen.

## [ LOCAL PROCESSING ]

Frames stay in the camera worker and are not saved by LockGuard. Before loading MediaPipe, the worker installs a seccomp filter blocking new IPv4/IPv6 sockets; Unix sockets remain available. The user service additionally restricts socket families. Installation downloads dependencies and the model, whose pinned SHA-256 is verified before use.

## [ OPERATION ]

The camera worker runs separately from the supervisor, so blocked capture or inference does not stop the supervisor's timeout checks. Pausing or detecting an already locked session releases the camera. State changes are logged to the journal without images or face identities. Protection requires the service to remain running.

Install from the repository root with `./build.sh`; after testing the screen locker, `./build.sh --start` enables camera protection.

See [installation](INSTALLATION.md), [configuration](docs/CONFIGURATION.md), and [validation](docs/TESTING.md). This is an additional privacy aid, not a replacement for authentication or the desktop's normal screen-lock policy.
