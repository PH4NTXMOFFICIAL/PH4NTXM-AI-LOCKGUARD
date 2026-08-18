# [ PH4NTXM AI LOCKGUARD ]

PH4NTXM AI LockGuard provides real-time privacy protection through AI-powered face detection.  
The system continuously monitors the local camera session and evaluates detected face presence without transmitting data or relying on external telemetry.  
When an unexpected additional face is detected or the owner is absent beyond the configured threshold, the active user session is automatically locked.  
All detection and security decisions operate locally on the protected system.

## [ PH4NTXM AI DETECTION ]

PH4NTXM AI LockGuard uses MediaPipe face detection to analyze camera frames in real time.  
The detection engine evaluates the number of visible faces and maintains local owner-presence state.  
No facial identity recognition or remote processing is required.

## [ SHOULDER-SURFING PROTECTION ]

When multiple faces are detected simultaneously, PH4NTXM AI LockGuard treats the event as a potential unauthorized viewing attempt.  
The security response is triggered immediately and the active session is locked.

## [ OWNER ABSENCE ]

When no face is detected, the system maintains an absence timer.  
If the configured absence threshold is exceeded, the session lockdown mechanism is triggered automatically.  
The default owner-missing threshold is five seconds.

## [ SESSION LOCKDOWN ]

Security events invoke the local panic mechanism which locks the active Linux user session.  
The lockdown operation is performed locally through the system session manager without transmitting security events or camera data externally.

## [ LOCAL OPERATION ]

All face detection and security decisions are processed locally on the protected machine.  
The system does not require cloud-based facial analysis, background telemetry, or remote services for its detection and lockdown mechanisms.

## [ SYSTEM SERVICE ]

PH4NTXM AI LockGuard can operate as a persistent system service and automatically restart after unexpected termination.  
The installation process creates the required Python environment, downloads the detection model, configures the service, and enables automatic startup.

## [ INSTALLATION ]

The project includes an automated installation script that prepares the runtime environment, installs required dependencies, downloads the MediaPipe detection model, and registers the LockGuard service.

## [ SUMMARY ]

PH4NTXM AI LockGuard provides local AI-assisted privacy protection through continuous face detection, owner-presence monitoring, shoulder-surfing detection, and automatic Linux session lockdown.  
The system operates locally, requires no remote telemetry, and is designed for lightweight continuous protection of unattended or actively used Linux sessions.