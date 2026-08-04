from __future__ import annotations
import functools, hmac, json, os, time
from pathlib import Path
import jwt, requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from server.policy import validate_command

PROJECT_ROOT = Path(__file__).resolve().parents[2]; STATIC_ROOT = Path(__file__).resolve().parent / "static"; load_dotenv(PROJECT_ROOT / ".env")
app = Flask(__name__, static_folder=str(STATIC_ROOT)); audit_path = PROJECT_ROOT / "audit.jsonl"
secret, key = os.environ["JWT_SECRET"], os.environ["GATEWAY_INTERNAL_KEY"]
gateway = os.getenv("GATEWAY_INTERNAL_URL", "http://127.0.0.1:8765")

def audit(entry):
    with audit_path.open("a", encoding="utf-8") as out: out.write(json.dumps({"time":time.time(), **entry}, ensure_ascii=False)+"\n")

def auth(admin=False):
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            token = request.headers.get("Authorization", "").removeprefix("Bearer ")
            try: request.user = jwt.decode(token, secret, algorithms=["HS256"])
            except jwt.InvalidTokenError: return jsonify(error="invalid or expired token"), 401
            if admin and request.user.get("role") != "admin": return jsonify(error="admin role required"), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorate

@app.get("/")
def home(): return send_from_directory(app.static_folder, "index.html")

@app.post("/api/login")
def login():
    body=request.get_json(silent=True) or {}
    if body.get("username") != os.getenv("ADMIN_USERNAME", "admin") or body.get("password") != os.getenv("ADMIN_PASSWORD", "change-this-password"):
        audit({"event":"login_failed","username":body.get("username")}); return jsonify(error="invalid credentials"), 401
    token=jwt.encode({"sub":body["username"],"role":"admin","iat":int(time.time()),"exp":int(time.time())+3600}, secret, algorithm="HS256")
    audit({"event":"login","username":body["username"]}); return jsonify(token=token, role="admin")

@app.get("/api/agents")
@auth()
def agents():
    response=requests.get(gateway+"/internal/agents", headers={"X-Gateway-Key":key}, timeout=5)
    return jsonify(response.json()), response.status_code

@app.post("/api/agents/<agent_id>/commands")
@auth()
def command(agent_id):
    body=request.get_json(silent=True) or {}; action=body.get("action"); payload=body.get("payload", {})
    error=validate_command(action, payload, request.user.get("role", "viewer"))
    if error:
        audit({"event":"command_denied","user":request.user["sub"],"agent_id":agent_id,"action":action,"reason":error}); return jsonify(error=error), 400
    try:
        response=requests.post(gateway+"/internal/command", headers={"X-Gateway-Key":key}, json={"agent_id":agent_id,"action":action,"payload":payload}, timeout=25)
        result=response.json() if response.headers.get("content-type", "").startswith("application/json") else {"error":response.text}
    except requests.RequestException as exc: result={"error":str(exc)}; response=type("R",(),{"status_code":502})()
    audit({"event":"command","user":request.user["sub"],"agent_id":agent_id,"action":action,"ok":result.get("ok",False)})
    return jsonify(result), response.status_code

@app.get("/api/audit")
@auth(admin=True)
def audit_entries():
    if not audit_path.exists(): return jsonify(entries=[])
    lines = audit_path.read_text(encoding="utf-8").splitlines()[-100:]
    entries = []
    for line in reversed(lines):
        try: entries.append(json.loads(line))
        except json.JSONDecodeError: pass
    return jsonify(entries=entries)


@app.post("/internal/gateway-event")
def gateway_event():
    """Private Gateway-to-Server audit endpoint; never exposed to the UI."""
    supplied = request.headers.get("X-Gateway-Key", "")
    if not supplied or not hmac.compare_digest(supplied, key):
        return jsonify(error="unauthorized gateway"), 401
    event = request.get_json(silent=True) or {}
    audit({"source": "gateway", **event})
    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(
        host=os.getenv("SERVER_HOST", os.getenv("BACKEND_HOST", "0.0.0.0")),
        port=int(os.getenv("SERVER_PORT", os.getenv("BACKEND_PORT", "5000"))),
        threaded=True,
    )
