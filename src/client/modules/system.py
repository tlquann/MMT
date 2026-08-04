from __future__ import annotations

import base64
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil


class SystemModules:
    def __init__(self) -> None:
        self.consent = os.getenv("REMOTE_ADMIN_CONSENT", "false").lower() == "true"
        self.file_root = Path(os.getenv("REMOTE_ADMIN_FILE_ROOT", str(Path.home() / "Documents"))).resolve()

    def processes(self) -> list[dict[str, Any]]:
        items = []
        for proc in psutil.process_iter(["pid", "name", "memory_info", "status"]):
            try:
                proc.cpu_percent(None)
                items.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(0.1)
        result = []
        for proc in items:
            try:
                info = proc.as_dict(attrs=["pid", "name", "memory_info", "status"])
                rss = info["memory_info"].rss
                result.append({"pid": info["pid"], "name": info["name"] or "unknown", "cpu_percent": round(proc.cpu_percent(None), 1), "ram_mb": round(rss / 1048576, 2), "status": info["status"]})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return sorted(result, key=lambda value: (-value["cpu_percent"], -value["ram_mb"]))

    def kill(self, pid: int) -> dict[str, Any]:
        if pid in {0, 4, os.getpid()}:
            return {"ok": False, "error": "protected process"}
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            if name.casefold() in {"system", "system idle process", "registry", "smss.exe", "csrss.exe", "wininit.exe"}:
                return {"ok": False, "error": "protected system process"}
            proc.kill(); proc.wait(3)
            return {"ok": True, "pid": pid, "name": name}
        except psutil.NoSuchProcess: return {"ok": False, "error": "process not found"}
        except psutil.AccessDenied: return {"ok": False, "error": "access denied"}
        except psutil.TimeoutExpired: return {"ok": False, "error": "termination timeout"}

    def applications(self) -> list[dict[str, Any]]:
        return self.processes()

    def open_application(self, app: str) -> dict[str, Any]:
        commands = {"notepad": ["notepad.exe"], "calculator": ["calc.exe"]}
        if app not in commands: return {"ok": False, "error": "application is not allow-listed"}
        subprocess.Popen(commands[app])
        return {"ok": True, "app": app}

    def list_files(self, relative_path: str) -> dict[str, Any]:
        root = self.file_root
        target = (root / relative_path).resolve()
        if root != target and root not in target.parents:
            return {"ok": False, "error": "path outside allowed root"}
        try:
            return {"ok": True, "root": str(root), "path": str(target.relative_to(root)), "items": [{"name": item.name, "is_dir": item.is_dir(), "size": item.stat().st_size if item.is_file() else None} for item in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))[:200]]}
        except OSError as error: return {"ok": False, "error": str(error)}

    def telemetry(self) -> dict[str, Any]:
        temperatures = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        values = [entry.current for group in temperatures.values() for entry in group if entry.current is not None]
        return {"ok": True, "uptime_seconds": int(time.time() - psutil.boot_time()), "cpu_percent": psutil.cpu_percent(0.1), "ram_percent": psutil.virtual_memory().percent, "temperature_c": round(max(values), 1) if values else None, "platform": platform.platform()}

    def power_action(self, operation: str) -> dict[str, Any]:
        if os.getenv("ALLOW_POWER_ACTIONS", "false").lower() != "true":
            return {"ok": False, "error": "power actions are disabled locally"}
        commands = {"lock": ["rundll32.exe", "user32.dll,LockWorkStation"], "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], "restart": ["shutdown", "/r", "/t", "15"], "shutdown": ["shutdown", "/s", "/t", "15"]}
        if operation not in commands: return {"ok": False, "error": "invalid power operation"}
        subprocess.Popen(commands[operation])
        return {"ok": True, "operation": operation}

    def snapshot(self, webcam: bool) -> dict[str, Any]:
        if not self.consent: return {"ok": False, "error": "local consent is disabled on this Agent"}
        try:
            if webcam:
                import cv2
                camera = cv2.VideoCapture(0); ok, frame = camera.read(); camera.release()
                if not ok: return {"ok": False, "error": "cannot read webcam"}
                ok, encoded = cv2.imencode(".jpg", frame)
                if not ok: return {"ok": False, "error": "cannot encode webcam frame"}
                data = encoded.tobytes()
            else:
                import mss
                from PIL import Image
                import io
                with mss.mss() as capture:
                    shot = capture.grab(capture.monitors[1])
                    image = Image.frombytes("RGB", shot.size, shot.rgb)
                    stream = io.BytesIO(); image.save(stream, format="JPEG", quality=70); data = stream.getvalue()
            return {"ok": True, "image_base64": base64.b64encode(data).decode("ascii")}
        except Exception as error: return {"ok": False, "error": str(error)}
