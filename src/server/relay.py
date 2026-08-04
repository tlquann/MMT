from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field

from aiohttp import web
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentSession:
    agent_id: str
    hostname: str
    websocket: web.WebSocketResponse
    connected_at: float = field(default_factory=time.time)
    pending: dict[str, asyncio.Future] = field(default_factory=dict)


class GatewayHub:
    def __init__(self, secret: str, internal_key: str):
        self.secret = secret
        self.internal_key = internal_key
        self.agents: dict[str, AgentSession] = {}

    async def audit_event(self, event: str, **details: object) -> None:
        """Best-effort connection audit delivery to the Server's private API."""
        server_url = os.getenv("SERVER_AUDIT_URL", "http://127.0.0.1:5000/internal/gateway-event")
        try:
            import aiohttp
            async with aiohttp.ClientSession() as client:
                await client.post(
                    server_url,
                    headers={"X-Gateway-Key": self.internal_key},
                    json={"event": event, **details},
                    timeout=aiohttp.ClientTimeout(total=2),
                )
        except Exception:
            # A missing Server must never terminate an authenticated Agent.
            pass

    async def agent_ws(self, request: web.Request) -> web.StreamResponse:
        ws = web.WebSocketResponse(max_msg_size=4 * 1024 * 1024, heartbeat=20)
        await ws.prepare(request)
        nonce = secrets.token_hex(32)
        await ws.send_json({"type": "challenge", "nonce": nonce})
        message = await ws.receive_json(timeout=10)
        expected = hmac.new(self.secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
        agent_id = message.get("agent_id")
        if message.get("type") != "auth" or not isinstance(agent_id, str) or not hmac.compare_digest(str(message.get("hmac", "")), expected):
            await self.audit_event("agent_auth_failed", address=request.remote)
            await ws.send_json({"type": "auth_error"})
            await ws.close()
            return ws
        session = AgentSession(agent_id, str(message.get("hostname") or agent_id), ws)
        previous = self.agents.get(agent_id)
        self.agents[agent_id] = session
        if previous:
            await previous.websocket.close()
        await ws.send_json({"type": "auth_ok", "agent_id": agent_id})
        await self.audit_event("agent_connected", agent_id=agent_id, hostname=session.hostname, address=request.remote)
        try:
            async for incoming in ws:
                if incoming.type != web.WSMsgType.TEXT:
                    continue
                response = incoming.json()
                request_id = response.get("request_id")
                future = session.pending.get(request_id)
                if response.get("type") == "response" and future and not future.done():
                    future.set_result(response)
        finally:
            if self.agents.get(agent_id) is session:
                del self.agents[agent_id]
            await self.audit_event("agent_disconnected", agent_id=agent_id, hostname=session.hostname)
            for future in session.pending.values():
                if not future.done():
                    future.set_exception(ConnectionError("agent disconnected"))
        return ws

    def _internal_allowed(self, request: web.Request) -> bool:
        return hmac.compare_digest(request.headers.get("X-Gateway-Key", ""), self.internal_key)

    async def list_agents(self, request: web.Request) -> web.Response:
        if not self._internal_allowed(request):
            raise web.HTTPUnauthorized()
        return web.json_response({"agents": [{"agent_id": item.agent_id, "hostname": item.hostname, "connected_at": item.connected_at} for item in self.agents.values()]})

    async def command(self, request: web.Request) -> web.Response:
        if not self._internal_allowed(request):
            raise web.HTTPUnauthorized()
        body = await request.json()
        session = self.agents.get(body.get("agent_id"))
        if not session:
            await self.audit_event("command_agent_unavailable", agent_id=body.get("agent_id"), action=body.get("action"))
            raise web.HTTPNotFound(text="agent is not connected")
        request_id = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        session.pending[request_id] = future
        try:
            await session.websocket.send_json({"type": "command", "request_id": request_id, "action": body.get("action"), "payload": body.get("payload", {})})
            result = await asyncio.wait_for(future, timeout=20)
            await self.audit_event("gateway_command_result", agent_id=session.agent_id, action=body.get("action"), ok=bool(result.get("ok")))
            return web.json_response(result)
        except asyncio.TimeoutError:
            raise web.HTTPGatewayTimeout(text="agent command timed out")
        finally:
            session.pending.pop(request_id, None)


def main() -> None:
    secret, internal = os.getenv("AGENT_SHARED_SECRET", ""), os.getenv("GATEWAY_INTERNAL_KEY", "")
    if len(secret) < 16 or len(internal) < 16:
        raise SystemExit("Set AGENT_SHARED_SECRET and GATEWAY_INTERNAL_KEY in .env")
    hub = GatewayHub(secret, internal)
    app = web.Application()
    app.add_routes([web.get("/ws/agent", hub.agent_ws), web.get("/internal/agents", hub.list_agents), web.post("/internal/command", hub.command)])
    web.run_app(app, host=os.getenv("GATEWAY_HOST", "0.0.0.0"), port=int(os.getenv("GATEWAY_PORT", "8765")))


if __name__ == "__main__":
    main()
