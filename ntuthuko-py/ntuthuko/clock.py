"""Clock in/out with a persisted punch queue (port of components/ClockOfflineSync.js).

Punches are appended to a queue and then synced. In the browser the queue
protected against being offline; on a server it protects against a crash
part-way through: anything left in the queue is replayed by the next sync().
"""
import threading

from .client import ntuthuko_client as c
from .client import now_iso

QUEUE_KEY = "clock_queue"
_lock = threading.RLock()
_time_entries = c.entities["TimeEntry"]


def open_entry(employee_id):
    """The employee's current entry that has no clock_out, if any."""
    return next((e for e in _time_entries.filter(employee_id=employee_id) if not e.get("clock_out")), None)


def punch(kind, employee_id):
    with _lock:
        queue = c.raw_get(QUEUE_KEY, [])
        queue.append({"type": kind, "employee_id": employee_id, "time": now_iso()})
        c.raw_set(QUEUE_KEY, queue)
        sync()


def sync():
    with _lock:
        queue = c.raw_get(QUEUE_KEY, [])
        while queue:
            op = queue[0]
            if op["type"] == "in":
                _time_entries.create(
                    {"employee_id": op["employee_id"], "date": op["time"][:10], "clock_in": op["time"]}
                )
            else:
                open_ = open_entry(op["employee_id"])
                if open_:
                    _time_entries.update(open_["id"], {"clock_out": op["time"]})
            queue.pop(0)
            c.raw_set(QUEUE_KEY, queue)  # persist progress after every op
