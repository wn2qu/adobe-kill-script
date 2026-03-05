"""
Adobe Kill Script — Nuclear Option
===================================
Terminates ALL Adobe / Creative Cloud processes, stops their Windows services,
and disables the scheduled tasks that respawn them.

Run as Administrator for full effect (services + scheduled tasks).
Without admin rights it will still force-kill every Adobe process it can reach.

Usage:
    python adobe_kill_script.py            # interactive (pause at end)
    python adobe_kill_script.py --silent   # no pause, for automation / Task Scheduler
"""

import ctypes
import os
import subprocess
import sys
import time
import re

# ────────────────────────────────────────────
# 1.  CONFIGURATION — add / remove names here
# ────────────────────────────────────────────

# Regex patterns matched (case-insensitive) against process names.
# Covers every known Adobe daemon, helper, updater and app.
ADOBE_PROCESS_PATTERNS: list[str] = [
    r"adobe",
    r"creative\s*cloud",
    r"CCXProcess",
    r"CCLibrary",
    r"CoreSync",
    r"AcroTray",
    r"Acrobat",
    r"Photoshop",
    r"Illustrator",
    r"Premiere",
    r"AfterFX",
    r"InDesign",
    r"Lightroom",
    r"Media\s*Encoder",
    r"Animate",
    r"Audition",
    r"Bridge",
    r"Dreamweaver",
    r"Dimension",
    r"XD",
    r"Substance",
    r"Fresco",
    r"Aero",
    r"AGSService",
    r"AGMService",
    r"AdobeIPCBroker",
    r"AdobeUpdate",
    r"AdobeGC",
    r"AdobeNotification",
    r"AdobeCollabSync",
    r"node\.exe.*adobe",       # node helpers spawned inside CC folders
    r"LogTransport",           # Adobe log shipper
    r"armsvc",                 # Adobe ARM service process
]

# Windows service names (exact, case-insensitive).
ADOBE_SERVICE_NAMES: list[str] = [
    "AdobeARMservice",
    "AdobeUpdateService",
    "AGSService",
    "AGMService",
    "AdobeFlashPlayerUpdateSvc",
]

# Scheduled-task names (substring match, case-insensitive).
ADOBE_TASK_PATTERNS: list[str] = [
    "Adobe Acrobat Update Task",
    "Adobe Creative Cloud",
    "Launch Adobe CCXProcess",
    "AdobeGCInvoker",
    "Adobe Flash Player",
]

# How many kill-passes to run (catches respawners).
KILL_PASSES = 3
PASS_DELAY_SEC = 1.5

# ────────────────────────────────────────────
# 2.  HELPERS
# ────────────────────────────────────────────

class Colors:
    """ANSI escape codes for terminal colour (Windows 10+ supports these)."""
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"


def is_admin() -> bool:
    """Return True if this script is running with Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _compiled_patterns() -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in ADOBE_PROCESS_PATTERNS]


def get_adobe_processes() -> list[dict]:
    """
    Use WMIC to list every running process, then filter against our patterns.
    Returns list of dicts: { 'name': str, 'pid': int, 'path': str }
    """
    try:
        # tasklist /FO CSV gives us Name,PID,Session,Session#,Mem
        raw = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        return []

    patterns = _compiled_patterns()
    results: list[dict] = []
    seen_pids: set[int] = set()

    for line in raw.strip().splitlines():
        # CSV columns: "Image Name","PID","Session Name","Session#","Mem Usage"
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) < 2:
            continue
        name = parts[0]
        try:
            pid = int(parts[1])
        except ValueError:
            continue

        # Skip ourselves
        if pid == os.getpid():
            continue

        for pat in patterns:
            if pat.search(name):
                if pid not in seen_pids:
                    seen_pids.add(pid)
                    results.append({"name": name, "pid": pid})
                break

    # Also do a secondary check via WMIC for command-line paths containing "adobe"
    try:
        wmic_raw = subprocess.check_output(
            ["wmic", "process", "get", "ProcessId,ExecutablePath", "/FORMAT:CSV"],
            text=True, creationflags=subprocess.CREATE_NO_WINDOW, stderr=subprocess.DEVNULL,
        )
        for line in wmic_raw.strip().splitlines():
            cols = line.strip().split(",")
            if len(cols) < 3:
                continue
            exe_path = cols[1].strip()
            try:
                pid = int(cols[2].strip())
            except ValueError:
                continue
            if pid == os.getpid() or pid in seen_pids:
                continue
            if re.search(r"adobe", exe_path, re.IGNORECASE):
                seen_pids.add(pid)
                proc_name = os.path.basename(exe_path) if exe_path else f"PID {pid}"
                results.append({"name": proc_name, "pid": pid})
    except Exception:
        pass  # WMIC may not be available on all editions

    return results


def kill_processes(procs: list[dict]) -> tuple[int, int]:
    """Force-kill every process in the list. Returns (killed, failed)."""
    killed = 0
    failed = 0
    for p in procs:
        try:
            subprocess.check_call(
                ["taskkill", "/F", "/PID", str(p["pid"])],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            print(f"  {Colors.RED}[KILLED]{Colors.RESET}  {p['name']}  (PID {p['pid']})")
            killed += 1
        except subprocess.CalledProcessError:
            print(f"  {Colors.YELLOW}[FAILED]{Colors.RESET}  {p['name']}  (PID {p['pid']}) — may already be dead")
            failed += 1
    return killed, failed


def stop_adobe_services() -> int:
    """Stop and disable Adobe Windows services. Returns count handled."""
    count = 0
    for svc in ADOBE_SERVICE_NAMES:
        # Stop
        ret = subprocess.run(
            ["sc", "stop", svc],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Disable (prevents auto-restart)
        ret2 = subprocess.run(
            ["sc", "config", svc, "start=", "disabled"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if ret.returncode == 0 or ret2.returncode == 0:
            print(f"  {Colors.RED}[STOPPED]{Colors.RESET}  Service: {svc}")
            count += 1
        else:
            # Service may not exist on this machine — that's fine
            print(f"  {Colors.YELLOW}[SKIP]{Colors.RESET}    Service: {svc} (not found or access denied)")
    return count


def disable_adobe_tasks() -> int:
    """Disable Adobe scheduled tasks so they cannot respawn processes."""
    count = 0
    try:
        raw = subprocess.check_output(
            ["schtasks", "/Query", "/FO", "CSV", "/NH"],
            text=True, creationflags=subprocess.CREATE_NO_WINDOW,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        print(f"  {Colors.YELLOW}[SKIP]{Colors.RESET}  Could not query scheduled tasks.")
        return 0

    for line in raw.strip().splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if not parts:
            continue
        task_path = parts[0]  # e.g. \Adobe Creative Cloud
        for pattern in ADOBE_TASK_PATTERNS:
            if pattern.lower() in task_path.lower():
                ret = subprocess.run(
                    ["schtasks", "/Change", "/TN", task_path, "/DISABLE"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if ret.returncode == 0:
                    print(f"  {Colors.RED}[DISABLED]{Colors.RESET} Task: {task_path}")
                    count += 1
                else:
                    print(f"  {Colors.YELLOW}[FAILED]{Colors.RESET}  Task: {task_path} (access denied?)")
                break
    return count


# ────────────────────────────────────────────
# 3.  MAIN
# ────────────────────────────────────────────

def main() -> None:
    os.system("")  # Enable ANSI on Windows

    print(f"\n{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}║     ADOBE KILL SCRIPT — NUCLEAR OPTION   ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚══════════════════════════════════════════╝{Colors.RESET}\n")

    admin = is_admin()
    if admin:
        print(f"  {Colors.GREEN}[✓] Running as Administrator{Colors.RESET}\n")
    else:
        print(f"  {Colors.YELLOW}[!] NOT running as Administrator.{Colors.RESET}")
        print(f"      Services & scheduled tasks may not be modifiable.")
        print(f"      Right-click → Run as administrator for full effect.\n")

    # ── Phase 1: Kill processes (multi-pass) ──────────────
    total_killed = 0
    for pass_num in range(1, KILL_PASSES + 1):
        procs = get_adobe_processes()
        if not procs:
            if pass_num == 1:
                print(f"  {Colors.GREEN}[✓] No Adobe processes detected.{Colors.RESET}")
            break

        print(f"  {Colors.BOLD}── Pass {pass_num}: found {len(procs)} Adobe process(es) ──{Colors.RESET}")
        killed, _ = kill_processes(procs)
        total_killed += killed

        if pass_num < KILL_PASSES:
            time.sleep(PASS_DELAY_SEC)  # wait for potential respawns

    # Final verification pass
    remaining = get_adobe_processes()
    if remaining:
        print(f"\n  {Colors.YELLOW}[!] {len(remaining)} stubborn process(es) survived:{Colors.RESET}")
        for p in remaining:
            print(f"      • {p['name']}  (PID {p['pid']})")
    else:
        if total_killed > 0:
            print(f"\n  {Colors.GREEN}[✓] All Adobe processes terminated.{Colors.RESET}")

    # ── Phase 2: Stop services ────────────────────────────
    print(f"\n  {Colors.BOLD}── Stopping Adobe Services ──{Colors.RESET}")
    if admin:
        stop_adobe_services()
    else:
        print(f"  {Colors.YELLOW}[SKIP]{Colors.RESET}  Need admin rights to stop services.")

    # ── Phase 3: Disable scheduled tasks ──────────────────
    print(f"\n  {Colors.BOLD}── Disabling Adobe Scheduled Tasks ──{Colors.RESET}")
    if admin:
        disable_adobe_tasks()
    else:
        print(f"  {Colors.YELLOW}[SKIP]{Colors.RESET}  Need admin rights to disable tasks.")

    # ── Summary ───────────────────────────────────────────
    print(f"\n{Colors.BOLD}{Colors.CYAN}══════════════════════════════════════════{Colors.RESET}")
    print(f"  {Colors.GREEN}Done.{Colors.RESET}  Killed {total_killed} process(es).")
    if not admin:
        print(f"  {Colors.YELLOW}Tip:{Colors.RESET} Re-run as admin to also stop services & tasks.")
    print(f"{Colors.BOLD}{Colors.CYAN}══════════════════════════════════════════{Colors.RESET}\n")

    if "--silent" not in sys.argv:
        input("  Press Enter to exit...")


if __name__ == "__main__":
    main()
