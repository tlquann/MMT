# Test guide

## 1. Prepare environment

```powershell
cd C:\Qun\Project-Code\E-DoAnMMT\remote_admin_platform
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
Copy-Item .env.example .env
```

Edit `.env`: replace `JWT_SECRET`, `AGENT_SHARED_SECRET`,
`GATEWAY_INTERNAL_KEY`, and `ADMIN_PASSWORD` with long unique values.

## 2. Run automated policy tests

```powershell
pytest -q
```

Expected result: three passing tests. They verify that unsupported shell-like
commands are rejected and that only an admin may request a process kill.

## 3. Run integration test on one PC

Open three terminals in the same project folder, activate `.venv` in each:

```powershell
python -m server.relay
```

```powershell
python -m server.dashboard
```

```powershell
python -m client.main
```

Open `http://127.0.0.1:5000`, log in with `ADMIN_USERNAME` and
`ADMIN_PASSWORD` from `.env`, then refresh Agents. The selected Agent should
be online; test `Processes` first and confirm that its list loads.

## 4. LAN test

Run `server.relay` and `server.dashboard` on the server PC. On a Client PC set
`GATEWAY_WS_URL=ws://<SERVER_LAN_IP>:8765/ws/agent`, use the identical
`AGENT_SHARED_SECRET`, then run `python -m client.main`. Allow TCP ports 5000
and 8765 through the Windows firewall only on the trusted LAN profile.

## 5. Feature verification

- Processes: load, search, then kill a disposable test process only.
- Files: browse only below `REMOTE_ADMIN_FILE_ROOT`.
- Screen/Webcam: first set `REMOTE_ADMIN_CONSENT=true` locally on the Agent.
- Power: keep `ALLOW_POWER_ACTIONS=false` during normal testing; test `lock`
  first when explicitly authorized.
- Audit: open the Audit tab or inspect `audit.jsonl` after each action.
