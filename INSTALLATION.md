# [ INSTALLATION ]

PH4NTXM AI LockGuard is a local AI-assisted privacy protection module designed for Linux systems.  
It provides continuous face detection, owner-presence monitoring, shoulder-surfing detection, and automatic session lockdown aligned with PH4NTXM operational assumptions.

## [ REQUIREMENTS ]

Debian-based systems:

sudo apt install python3 python3-pip python3-venv

A functional webcam and an active graphical user session are required.

## [ INSTALLATION ]

From inside the module directory ph4ntxm-ai-lockguard:

chmod +x install.sh

./install.sh

The installation process creates the required Python environment, installs dependencies, downloads the face detection model, configures the system service, and starts PH4NTXM AI LockGuard automatically.

## [ USAGE ]

PH4NTXM AI LockGuard operates as a systemd service after installation.

Service status:

systemctl status ph4ntxm-lockguard.service

Service logs:

journalctl -u ph4ntxm-lockguard.service

The default configuration monitors the primary camera and triggers session lockdown when multiple faces are detected or when no face is detected for the configured owner-missing timeout.

## [ CUSTOMIZATION NOTES ]

This module was originally developed for the PH4NTXM operational environment and reflects assumptions, thresholds, and runtime expectations specific to that ecosystem.  
Users deploying the module on external systems may wish to modify detection thresholds, owner-missing timeout values, camera selection, sampling parameters, panic cooldown behavior, or session lockdown mechanisms according to their own environment and workflow requirements.

## [ UNINSTALLATION ]

From inside the module directory ph4ntxm-ai-lockguard:

chmod +x uninstall.sh

./uninstall.sh

The uninstall process disables the system service and removes the locally installed runtime environment, detection model, and generated log files.

## [ NOTES ]

PH4NTXM AI LockGuard processes camera frames locally and does not require external AI services or remote telemetry for face detection.  
The module detects face presence and face count and does not perform facial identity recognition.

Some installation and service operations require elevated privileges depending on system configuration and system policies.