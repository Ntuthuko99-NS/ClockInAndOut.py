"""JSON-file backed client (port of src/api/ntuthukoClient.js).

Same shape as the original: ``client.entities["Employee"].list() / filter() /
create() / update() / delete()`` and ``client.auth.me()``. Replace the internals
with a real database when you need one; callers don't have to change.
"""
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import ENTITY_NAMES

DEFAULT_ME = {"id": "me", "full_name": "Demo User", "email": "demo@example.com", "role": "admin"}


def now_iso() -> str:
    """UTC timestamp like JavaScript's Date#toISOString (e.g. 2026-10-13T08:00:00.000Z)."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Entity:
    def __init__(self, client: "NtuthukoClient", name: str):
        self._client = client
        self.name = name

    def list(self) -> list:
        return self._client._get(self.name, [])

    def filter(self, **query) -> list:
        return [x for x in self.list() if all(x.get(k) == v for k, v in query.items())]

    def create(self, data: dict) -> dict:
        record = {**data, "id": str(uuid.uuid4()), "created_date": now_iso()}
        with self._client._lock:
            items = self.list()
            items.append(record)
            self._client._set(self.name, items)
        return record

    def update(self, id: str, data: dict) -> None:
        with self._client._lock:
            items = [{**x, **data} if x.get("id") == id else x for x in self.list()]
            self._client._set(self.name, items)

    def delete(self, id: str) -> None:
        with self._client._lock:
            self._client._set(self.name, [x for x in self.list() if x.get("id") != id])


class Auth:
    def __init__(self, client: "NtuthukoClient"):
        self._client = client

    def me(self) -> dict:
        return self._client._get("me", None) or dict(DEFAULT_ME)


class NtuthukoClient:
    def __init__(self, path=None):
        self._lock = threading.RLock()
        self.path = Path(path or os.environ.get("NTUTHUKO_DATA", "ntuthuko_data.json"))
        self.entities = {name: Entity(self, name) for name in ENTITY_NAMES}
        self.auth = Auth(self)

    def configure(self, path) -> None:
        self.path = Path(path)

    # --- raw key/value storage (also used for the clock queue) -------------
    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def _get(self, key, default):
        with self._lock:
            return self._load().get(key, default)

    def _set(self, key, value) -> None:
        with self._lock:
            data = self._load()
            data[key] = value
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)  # atomic: never leaves a half-written file

    def raw_get(self, key, default=None):
        return self._get(key, default)

    def raw_set(self, key, value) -> None:
        self._set(key, value)


ntuthuko_client = NtuthukoClient()
