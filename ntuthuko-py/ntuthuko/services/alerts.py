"""Port of src/services/AlertService.js."""
from dataclasses import asdict
from datetime import datetime, timedelta

from ..client import ntuthuko_client
from ..models import Alert
from ..ui import parse_iso

_alerts = ntuthuko_client.entities["Alert"]


class AlertService:
    @staticmethod
    def create(type, message, employee_id=None):
        data = {k: v for k, v in asdict(Alert(type, message, employee_id)).items() if v is not None}
        return _alerts.create(data)

    @staticmethod
    def unread():
        return _alerts.filter(read=False)

    @staticmethod
    def mark_read(id):
        return _alerts.update(id, {"read": True})

    @classmethod
    def check_late(cls, employee, shift, clock_in, grace_min=10):
        # Shift times are local wall-clock times (naive); clock_in is a UTC ISO string.
        start = datetime.fromisoformat(f"{shift['date']}T{shift['start_time']}").astimezone()
        due = start + timedelta(minutes=grace_min)
        if parse_iso(clock_in) > due:
            return cls.create("late", f"{employee['full_name']} clocked in late", employee["id"])
