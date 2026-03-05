# Adobe Kill Script

A single-file Python script that **completely terminates all Adobe and Creative Cloud processes** on Windows — including the stubborn background daemons, services, and scheduled tasks that respawn them.

## The Problem

Adobe Creative Cloud installs a web of persistent background processes, Windows services, and scheduled tasks that:

- Run constantly even when no Adobe app is open
- Respawn each other when individually killed
- Consume RAM, CPU, and network bandwidth 24/7
- Cannot be fully stopped by simply closing the Creative Cloud app

Killing `Creative Cloud.exe` isn't enough — `AdobeIPCBroker`, `CoreSync`, `CCXProcess`, `AdobeUpdateService`, and others will just relaunch it (or each other).

## What It Does

The script operates in **3 phases** with **3 kill passes** to defeat respawn chains:

| Phase | Action | Admin Required? |
|-------|--------|:---------------:|
| **1. Kill Processes** | Force-terminates all Adobe processes (3 passes with delay to catch respawns) | No* |
| **2. Stop Services** | Stops and disables Adobe Windows services (`AdobeUpdateService`, `AdobeARMservice`, etc.) | Yes |
| **3. Disable Tasks** | Disables Adobe scheduled tasks that restart processes (`Adobe Creative Cloud`, `Launch Adobe CCXProcess`, etc.) | Yes |

\*Some protected system-level processes (e.g., `AdobeUpdateService.exe`) require admin rights to kill.

### Processes Detected & Killed

Matches **30+ patterns** including all major apps and background daemons:

<details>
<summary>Full process list (click to expand)</summary>

**Background Daemons:**
- Adobe Desktop Service
- AdobeIPCBroker
- AdobeUpdateService
- CCXProcess
- CCLibrary
- CoreSync
- Creative Cloud / Creative Cloud Helper / Creative Cloud UI Helper
- AdobeNotificationClient
- AdobeGCClient
- AdobeCollabSync
- LogTransport
- AGSService / AGMService
- AcroTray / armsvc

**Applications (also killed if running):**
- Photoshop, Illustrator, Premiere Pro, After Effects
- InDesign, Lightroom, Media Encoder, Audition
- Animate, Bridge, Dreamweaver, Dimension, XD
- Substance 3D, Fresco, Aero, Acrobat

</details>

## Requirements

- **OS:** Windows 10 / 11
- **Python:** 3.10+
- **No dependencies** — uses only the Python standard library

## Usage

### Basic (interactive)

```
python adobe_kill_script.py
```

Displays results and waits for Enter at the end.

### Silent mode (for automation)

```
python adobe_kill_script.py --silent
```

No pause — suitable for batch files, Task Scheduler, or startup scripts.

### Full power (recommended)

Right-click your terminal → **Run as administrator**, then:

```
python adobe_kill_script.py
```

Without admin rights, the script will still kill every process it can, but it cannot stop Windows services or disable scheduled tasks.

## Example Output

```
╔══════════════════════════════════════════╗
║     ADOBE KILL SCRIPT — NUCLEAR OPTION   ║
╚══════════════════════════════════════════╝

  [✓] Running as Administrator

  ── Pass 1: found 13 Adobe process(es) ──
  [KILLED]  Creative Cloud.exe          (PID 18912)
  [KILLED]  AdobeIPCBroker.exe          (PID 24724)
  [KILLED]  Adobe Desktop Service.exe   (PID 4184)
  [KILLED]  Creative Cloud Helper.exe   (PID 16872)
  [KILLED]  CCXProcess.exe              (PID 18796)
  [KILLED]  CoreSync.exe                (PID 6128)
  ...

  [✓] All Adobe processes terminated.

  ── Stopping Adobe Services ──
  [STOPPED]  Service: AdobeUpdateService
  [STOPPED]  Service: AdobeARMservice

  ── Disabling Adobe Scheduled Tasks ──
  [DISABLED] Task: \Adobe Creative Cloud
  [DISABLED] Task: \Launch Adobe CCXProcess
  [DISABLED] Task: \Adobe Acrobat Update Task

══════════════════════════════════════════
  Done.  Killed 13 process(es).
══════════════════════════════════════════
```

## Re-enabling Adobe Services

If you want to undo the service/task changes and let Adobe run normally again:

```powershell
# Re-enable services
sc config AdobeUpdateService start= auto
sc config AdobeARMservice start= auto
sc start AdobeUpdateService

# Re-enable scheduled tasks
schtasks /Change /TN "\Adobe Creative Cloud" /ENABLE
schtasks /Change /TN "\Launch Adobe CCXProcess" /ENABLE
schtasks /Change /TN "\Adobe Acrobat Update Task" /ENABLE
```

## Customization

All process patterns, service names, and task patterns are defined at the top of the script in clearly labeled lists. Add or remove entries to match your setup:

```python
ADOBE_PROCESS_PATTERNS: list[str] = [
    r"adobe",
    r"creative\s*cloud",
    # add your own patterns here...
]
```

## License

MIT — do whatever you want with it.

## Contributing

PRs welcome. If you find an Adobe process that slips through the cracks, open an issue with the process name and path.
