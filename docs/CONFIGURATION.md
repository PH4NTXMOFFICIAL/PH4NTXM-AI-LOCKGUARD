# [ CONFIGURATION ]

Edit `ph4ntxm-ai-lockguard/lockguard.toml`, then restart the user service. `lock_backend = "light-locker"` uses the native Light Locker command on X11; select `"loginctl"` only after testing that path on your desktop. Failure never falls back to another backend. Lock confirmation allows up to 15 seconds per attempt for the greeter transition. Defaults: camera 0, 320×240 maximum processing size, 5 FPS, confidence 0.5, absence timeout 5 seconds, and three consecutive multiple-face frames. Camera drivers may capture at a different resolution; frames are resized before detection.

`startup_timeout` allows 20 seconds for initialization; `camera_timeout` allows 5 seconds after the last valid frame. `lock_on_camera_loss = true` requests locking on failure. Setting it to false only reports the failure and retries capture, leaving the session unprotected while the camera is unavailable.

Pause and release the camera:

```bash
systemctl --user kill --kill-whom=main --signal=SIGUSR1 ph4ntxm-lockguard.service
```

Resume:

```bash
systemctl --user kill --kill-whom=main --signal=SIGUSR2 ph4ntxm-lockguard.service
```

Pause lasts until resume or service restart. Read state with `.venv/bin/python ph4ntxm_lockguard.py --status` from the application directory. Logs are available through `journalctl --user -u ph4ntxm-lockguard.service`.

For multiple graphical sessions, supply `--session SESSION_ID` when running manually, or replace the service's `ExecStart` through a user-service override. Only active, local sessions belonging to the same user are accepted. Settings previously passed through camera/timing command-line flags now belong in the TOML file.

There is no fixed `MemoryMax`: measure the complete service with your camera before adding a limit through `systemctl --user edit ph4ntxm-lockguard.service`. A limit that kills the supervisor also interrupts protection. Higher resolution/FPS increases resource use; low resolution, lighting and occlusion affect detection reliability.
