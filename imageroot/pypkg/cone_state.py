# SPDX-License-Identifier: GPL-3.0-or-later
"""Small module-owned file primitives. Operational steps live in actions."""
import contextlib
import fcntl
import json
import os
import re
import tempfile
from pathlib import Path

DEFAULTS = {
    "host": "", "lets_encrypt": False, "idp_provider": "", "user_domain": "",
    "explorer_enabled": True, "session_idle_s": 1800, "session_max_s": 28800,
    "independent_review": True, "query_candidate_limit": 5000,
    "max_readable_scopes": 500, "query_time_budget_ms": 10000,
    "backend_timeout_s": 5,
}

def private_dir():
    return Path(os.environ["AGENT_STATE_DIR"]) / "private"

def contracts():
    return json.loads((Path(os.environ["AGENT_INSTALL_DIR"]) / "etc/integration-lock.json").read_text())

def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default

@contextlib.contextmanager
def state_lock():
    private = private_dir()
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    private.chmod(0o700)
    with (private / ".lock").open("a") as stream:
        os.chmod(stream.name, 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield private

def atomic_write(path, text, mode=0o600):
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def write_json(path, data):
    atomic_write(path, json.dumps(data, indent=2) + "\n")

def env_text(values):
    # Podman env files use raw KEY=value entries, without shell quoting.
    entries = []
    for key, value in sorted(values.items()):
        value = str(value)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or any(c in value for c in "\r\n\x00"):
            raise ValueError("Unsafe environment entry")
        entries.append(key + "=" + value + "\n")
    return "".join(entries)

def validate_settings(request):
    # Framework validates the JSON schema; these are cross-field constraints.
    if request["session_max_s"] < request["session_idle_s"]:
        return "session_max_s", "session_max_before_idle"
    return None
