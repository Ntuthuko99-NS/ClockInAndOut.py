"""Framework-independent helpers shared by the Flask and Streamlit front ends."""
from .client import ntuthuko_client as c
from .models import SETTINGS_DEFAULTS
from .ui import today

E = c.entities


def get_settings() -> dict:
    items = E["CompanySettings"].list()
    return items[0] if items else {}


def employee_names(employees) -> dict:
    return {e["id"]: e.get("full_name", "") for e in employees}


def setting(settings: dict, key: str):
    """settings[key] ?? default (JavaScript's nullish coalescing)."""
    value = settings.get(key)
    return SETTINGS_DEFAULTS[key] if value is None else value


def team_availability(employees, entries, leave):
    d = today()
    rows = []
    for e in employees:
        if any(
            l["employee_id"] == e["id"] and l.get("status") == "approved" and l["start_date"] <= d <= l["end_date"]
            for l in leave
        ):
            rows.append((e["full_name"], "On leave", "text-amber-700"))
        elif any(x["employee_id"] == e["id"] and not x.get("clock_out") for x in entries):
            rows.append((e["full_name"], "Working", "text-emerald-700"))
        else:
            rows.append((e["full_name"], "Not in", "text-gray-500"))
    return rows
