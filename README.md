# Remote Administration Platform

This is the consolidated active Python project for LAN remote administration.

## Components

- `server.dashboard`: Flask web application; it owns JWT, RBAC, policy, audit, and proxying.
- `server.relay`: aiohttp WebSocket hub for authenticated Agents.
- `client`: outbound WebSocket client and local management modules.
- `server`: command allow-list and role policy.
- `web`: static dark-mode dashboard served by `server.dashboard`.

## Security controls

- User requests require a signed, expiring JWT.
- Agent WebSocket handshakes use a nonce plus `AGENT_SHARED_SECRET` HMAC.
- `server.dashboard` validates every action against the shared command allow-list before `server.relay` forwarding.
- `server.relay` connection events and command results are written to `server.dashboard` `audit.jsonl` through an authenticated internal endpoint.
- Screen/Webcam require the local Client consent flag; power actions need a second local flag.
- Keyboard capture is intentionally unsupported and disabled.

## Run

```powershell
cd C:\Qun\Project-Code\E-DoAnMMT\remote_admin_platform
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
Copy-Item .env.example .env
python -m server.relay
```

Run `python -m server.dashboard` in another terminal. On each managed PC set
`GATEWAY_WS_URL=ws://<gateway-lan-ip>:8765/ws/agent` in local `.env`, then run
`python -m client.main`.
