# Architecture and source inventory

## Active data flow

```text
Browser -- HTTPS + JWT --> server.dashboard -- internal HTTP --> server.relay
                                                                     |
                                                                WSS + HMAC
                                                                     |
                                                                  Client
```

The browser has no Client socket route or Client credentials. `server.dashboard` validates the role and command schema, writes audit data, then asks `server.relay` to forward the command.

## Selection from the old workspace

| Existing location | Decision | Reason |
|---|---|---|
| `remote_admin_ws/` | Consolidated here | Current Python WebSocket implementation. |
| `remote_pc_monitor/` | Legacy reference | Raw TCP prototype superseded by WebSocket. |
| `stream/stream/` | Legacy reference | Camera-only Flask demo with runtime files. |
| `drive-download-*` | Archive only | Unrelated C++ prototype. |
| `ARM64-*/Debug` | Exclude | Compiler output, not source. |
| `Mạng máy tính.pdf` | Documentation archive | Not runtime code. |

## Module ownership

| Module | Handler | Controls |
|---|---|---|
| Applications | `applications/open_application/kill` | allow-list and admin action |
| Processes | `processes/kill` | PID and protected-name checks |
| Screen | `snapshot(False)` | local consent |
| Files | `list_files` | root and traversal checks |
| Webcam | `snapshot(True)` | local consent |
| Power | `telemetry/power_action` | admin plus local enable flag |
| Keyboard capture | `keylogger.py` | intentionally disabled by privacy policy |

The `src/client/modules/system.py` module is the local capability boundary for the Client. It can be split into focused modules later without changing the Relay protocol.
