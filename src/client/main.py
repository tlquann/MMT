from __future__ import annotations
import asyncio, hashlib, hmac, json, os, platform
from dotenv import load_dotenv
import websockets
from client.modules.system import SystemModules

load_dotenv()

async def run() -> None:
    modules = SystemModules()
    secret = os.environ["AGENT_SHARED_SECRET"]
    agent_id = os.getenv("AGENT_ID", platform.node())
    url = os.getenv("GATEWAY_WS_URL", "ws://127.0.0.1:8765/ws/agent")
    backoff = 3

    while True:
        try:
            async with websockets.connect(url, max_size=4 * 1024 * 1024, ping_interval=20) as ws:
                backoff = 3  # reset on successful connection
                challenge = json.loads(await ws.recv())
                signature = hmac.new(secret.encode(), challenge["nonce"].encode(), hashlib.sha256).hexdigest()
                await ws.send(json.dumps({
                    "type": "auth",
                    "agent_id": agent_id,
                    "hostname": platform.node(),
                    "hmac": signature,
                }))
                if json.loads(await ws.recv()).get("type") != "auth_ok":
                    raise ConnectionError("authentication failed")

                async for raw in ws:
                    command = json.loads(raw)
                    payload = command.get("payload", {})
                    action = command.get("action")

                    if action in {"LIST_PROCESSES", "LIST_APPLICATIONS"}:
                        result = {"ok": True, "items": modules.processes()}
                    elif action in {"KILL_PROCESS", "CLOSE_APPLICATION"}:
                        result = modules.kill(payload["pid"])
                    elif action == "OPEN_APPLICATION":
                        result = modules.open_application(payload["app"])
                    elif action == "OPEN_APPLICATION_BY_PATH":
                        result = modules.open_application_by_path(payload["path"])
                    elif action == "LIST_FILES":
                        result = modules.list_files(payload.get("path", ""))
                    elif action == "GET_TELEMETRY":
                        result = modules.telemetry()
                    elif action == "POWER_ACTION":
                        result = modules.power_action(payload["operation"])
                    elif action == "SCREEN_SNAPSHOT":
                        result = modules.snapshot(False)
                    elif action == "WEBCAM_SNAPSHOT":
                        result = modules.snapshot(True)
                    else:
                        result = {"ok": False, "error": "unsupported action"}

                    await ws.send(json.dumps({
                        "type": "response",
                        "request_id": command.get("request_id"),
                        **result,
                    }))
        except Exception as error:
            print(f"agent reconnecting in {backoff}s: {error}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)  # exponential backoff, cap at 60s


if __name__ == "__main__":
    asyncio.run(run())