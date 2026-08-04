from __future__ import annotations

COMMANDS = {
    "LIST_APPLICATIONS":         "operator",
    "OPEN_APPLICATION":          "admin",
    "OPEN_APPLICATION_BY_PATH":  "admin",
    "CLOSE_APPLICATION":         "admin",
    "LIST_PROCESSES":            "operator",
    "KILL_PROCESS":              "admin",
    "LIST_FILES":                "operator",
    "GET_TELEMETRY":             "operator",
    "POWER_ACTION":              "admin",
    "SCREEN_SNAPSHOT":           "admin",
    "WEBCAM_SNAPSHOT":           "admin",
}
RANK = {"viewer": 0, "operator": 1, "admin": 2}


def validate_command(action: object, payload: object, role: str) -> str | None:
    if action not in COMMANDS:
        return "command is not allow-listed"
    if RANK.get(role, -1) < RANK[COMMANDS[action]]:
        return "insufficient role"
    if not isinstance(payload, dict):
        return "payload must be an object"
    if action in {"KILL_PROCESS", "CLOSE_APPLICATION"} and (
        not isinstance(payload.get("pid"), int) or payload["pid"] <= 0
    ):
        return "pid must be a positive integer"
    if action == "OPEN_APPLICATION" and payload.get("app") not in {"notepad", "calculator"}:
        return "application is not allow-listed"
    if action == "OPEN_APPLICATION_BY_PATH":
        path = payload.get("path", "")
        if not isinstance(path, str) or not path.strip():
            return "path must be a non-empty string"
    if action == "POWER_ACTION" and payload.get("operation") not in {"lock", "sleep", "restart", "shutdown"}:
        return "invalid power operation"
    if action == "LIST_FILES" and not isinstance(payload.get("path", ""), str):
        return "path must be a string"
    return None