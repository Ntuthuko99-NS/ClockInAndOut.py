"""Entity schemas (port of src/entities/*.json) as dataclasses.

Records are stored as plain dicts (see client.py); these classes document the
fields, hold defaults and expose the allowed enum values used by the forms.
"""
from dataclasses import asdict, dataclass
from typing import Optional

ALERT_TYPES = ("late", "leave", "system", "info")
EMPLOYEE_STATUSES = ("active", "inactive")
LEAVE_TYPES = ("annual", "sick", "family", "unpaid", "other")
LEAVE_STATUSES = ("pending", "approved", "rejected", "cancelled")

ENTITY_NAMES = ("Employee", "Shift", "TimeEntry", "LeaveRequest", "Alert", "CompanySettings")


@dataclass
class Alert:
    type: str  # one of ALERT_TYPES
    message: str
    employee_id: Optional[str] = None
    read: bool = False


@dataclass
class CompanySettings:
    company_name: str = ""
    standard_hours_per_day: float = 8
    overtime_threshold_hours: float = 40
    annual_leave_days: float = 15
    sick_leave_days: float = 30
    late_grace_minutes: float = 10
    whatsapp_enabled: bool = False
    whatsapp_number: str = ""


@dataclass
class Employee:
    full_name: str
    email: str
    phone: str = ""
    role: str = ""
    department: str = ""
    hourly_rate: float = 0
    status: str = "active"  # one of EMPLOYEE_STATUSES


@dataclass
class LeaveRequest:
    employee_id: str
    leave_type: str  # one of LEAVE_TYPES
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    days: float = 0
    reason: str = ""
    status: str = "pending"  # one of LEAVE_STATUSES


@dataclass
class Shift:
    employee_id: str
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    notes: str = ""


@dataclass
class TimeEntry:
    employee_id: str
    clock_in: str  # ISO-8601 date-time
    date: str = ""  # YYYY-MM-DD
    clock_out: Optional[str] = None


SETTINGS_DEFAULTS = asdict(CompanySettings())
