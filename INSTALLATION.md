# [ INSTALLATION ]

The automated installer targets Debian 13 and Ubuntu 24.04 or newer on x86-64/AArch64, with Python 3.11+, systemd/logind and a graphical user session. Internet access and sudo rights are required for missing system packages. The default locking backend uses Light Locker on X11 with LightDM.

From the repository root, run as your normal desktop user:

```bash
./build.sh
```

The script installs missing APT dependencies, creates or repairs `.venv` including pip, installs Python requirements, verifies the downloaded model and creates the systemd user service. It requests sudo only for APT. Keep the repository writable by your user; do not run the whole script with sudo or move the directory after installation.

Before first activation, run `./ph4ntxm-ai-lockguard/panic.sh` and confirm both locking and password-protected unlocking. If Light Locker was newly installed, log out and back into LightDM first. Then enable and start protection:

```bash
./build.sh --start
```

`--start` checks configuration, model, session and locker prerequisites before enabling the service. Service startup does not prove the camera is ready: check `.venv/bin/python ph4ntxm_lockguard.py --status` from the application directory for Armed, and complete the [live checks](docs/TESTING.md). Camera loss or absence can trigger locking immediately after the configured timeout.

On updates, a running LockGuard service is stopped before its environment is changed and restarted after successful validation. If updating fails, protection stays stopped until repaired. An inactive service remains inactive unless `--start` is supplied. Automatic login startup requires the desktop to activate `graphical-session.target`.

The application-directory `./install.sh` accepts the same options. See [configuration](docs/CONFIGURATION.md) for pause/resume and other lockers. Run `./ph4ntxm-ai-lockguard/uninstall.sh` to remove the user service, environment and model; APT packages and journal entries remain.
