"""Routes - one section per page of the original src/pages/*.jsx."""
import calendar
from datetime import date
from urllib.parse import quote

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import clock
from .client import ntuthuko_client as c
from .logic import employee_names as _names
from .logic import get_settings as _settings
from .logic import setting as _setting
from .logic import team_availability as _team_availability
from .models import EMPLOYEE_STATUSES, LEAVE_TYPES, SETTINGS_DEFAULTS
from .services.alerts import AlertService
from .ui import hours, num, today

bp = Blueprint("pages", __name__)
E = c.entities


# --- helpers ---------------------------------------------------------------
def _employee_options(employees, blank_label):
    return [("", blank_label)] + [(e["id"], e["full_name"]) for e in employees]



# --- Dashboard -------------------------------------------------------------
@bp.get("/")
def dashboard():
    me = c.auth.me()
    clock.sync()
    employees, entries = E["Employee"].list(), E["TimeEntry"].list()
    leave, alerts = E["LeaveRequest"].list(), E["Alert"].list()
    active = [e for e in entries if not e.get("clock_out")]
    return render_template(
        "dashboard.html",
        me=me,
        open_entry=clock.open_entry(me["id"]),
        names=_names(employees),
        stats=[
            ("Employees", len(employees)),
            ("Clocked in", len(active)),
            ("Pending leave", sum(1 for l in leave if l.get("status") == "pending")),
            ("Unread alerts", sum(1 for a in alerts if not a.get("read"))),
        ],
        active=active,
        recent=sorted(entries, key=lambda e: e["clock_in"], reverse=True)[:8],
        availability=_team_availability(employees, entries, leave),
    )


@bp.post("/clock")
def clock_punch():
    """Clock widget button: clocks the current user in, or out if already in."""
    me = c.auth.me()
    clock.sync()
    clock.punch("out" if clock.open_entry(me["id"]) else "in", me["id"])
    return redirect(url_for("pages.profile" if request.form.get("next") == "profile" else "pages.dashboard"))


# --- Employees -------------------------------------------------------------
@bp.get("/employees")
def employees():
    items = E["Employee"].list()
    edit_id, edit = request.args.get("edit"), None
    if edit_id == "new":
        edit = {}
    elif edit_id:
        edit = next((e for e in items if e["id"] == edit_id), None)
        if edit is None:
            return redirect(url_for("pages.employees"))
    return render_template("employees.html", items=items, edit=edit, statuses=EMPLOYEE_STATUSES)


@bp.post("/employees/save")
def employee_save():
    f = request.form
    data = {
        "full_name": f.get("full_name", "").strip(),
        "email": f.get("email", "").strip(),
        "phone": f.get("phone", ""),
        "role": f.get("role", ""),
        "department": f.get("department", ""),
        "hourly_rate": num(f.get("hourly_rate")),
        "status": f.get("status") if f.get("status") in EMPLOYEE_STATUSES else "active",
    }
    emp_id = f.get("id")
    if not data["full_name"] or not data["email"]:
        flash("Full name and email are required.")
        return redirect(url_for("pages.employees", edit=emp_id or "new"))
    if emp_id:
        E["Employee"].update(emp_id, data)
    else:
        E["Employee"].create(data)
    return redirect(url_for("pages.employees"))


@bp.post("/employees/<id>/delete")
def employee_delete(id):
    E["Employee"].delete(id)
    return redirect(url_for("pages.employees"))


# --- Shifts ----------------------------------------------------------------
@bp.get("/shifts")
def shifts():
    employees_ = E["Employee"].list()
    return render_template(
        "shifts.html",
        employee_options=_employee_options(employees_, "Select employee"),
        names=_names(employees_),
        shifts=sorted(E["Shift"].list(), key=lambda s: s["date"]),
        today=today(),
    )


@bp.post("/shifts")
def shift_create():
    f = request.form
    if not f.get("employee_id"):
        flash("Select an employee.")
        return redirect(url_for("pages.shifts"))
    E["Shift"].create(
        {
            "employee_id": f["employee_id"],
            "date": f.get("date") or today(),
            "start_time": f.get("start_time", "08:00"),
            "end_time": f.get("end_time", "17:00"),
            "notes": f.get("notes", ""),
        }
    )
    return redirect(url_for("pages.shifts"))


@bp.post("/shifts/<id>/delete")
def shift_delete(id):
    E["Shift"].delete(id)
    return redirect(url_for("pages.shifts"))


# --- Leave -----------------------------------------------------------------
@bp.get("/leave")
def leave():
    me = c.auth.me()
    reqs, employees_ = E["LeaveRequest"].list(), E["Employee"].list()
    settings = _settings()
    mine = [r for r in reqs if r["employee_id"] == me["id"]]
    is_admin = me.get("role") == "admin"

    def used(t):
        return sum(r.get("days") or 0 for r in mine if r.get("leave_type") == t and r.get("status") == "approved")

    balance = []
    for label, t, key in (("Annual", "annual", "annual_leave_days"), ("Sick", "sick", "sick_leave_days")):
        total = _setting(settings, key)
        balance.append((label, total - used(t), total))

    today_ = date.today()
    days_in_month = calendar.monthrange(today_.year, today_.month)[1]
    cal_days = []
    for d in range(1, days_in_month + 1):
        iso = f"{today_.year}-{today_.month:02d}-{d:02d}"
        off = sum(1 for r in reqs if r.get("status") == "approved" and r["start_date"] <= iso <= r["end_date"])
        cal_days.append((d, off))

    by_id = {e["id"]: e for e in employees_}
    visible = [(r, by_id.get(r["employee_id"], me)) for r in (reqs if is_admin else mine)]
    return render_template(
        "leave.html",
        me=me,
        is_admin=is_admin,
        balance=balance,
        cal_label=today_.strftime("%B %Y"),
        cal_days=cal_days,
        visible=visible,
        leave_types=LEAVE_TYPES,
        today=today(),
    )


@bp.post("/leave")
def leave_request():
    me, f = c.auth.me(), request.form
    leave_type = f.get("leave_type", "annual")
    try:
        start, end = date.fromisoformat(f.get("start_date", "")), date.fromisoformat(f.get("end_date", ""))
    except ValueError:
        flash("Enter valid start and end dates.")
        return redirect(url_for("pages.leave"))
    days = (end - start).days + 1
    if days < 1 or leave_type not in LEAVE_TYPES:
        flash("The end date must be on or after the start date.")
        return redirect(url_for("pages.leave"))
    E["LeaveRequest"].create(
        {
            "leave_type": leave_type,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "reason": f.get("reason", ""),
            "days": days,
            "employee_id": me["id"],
            "status": "pending",
        }
    )
    return redirect(url_for("pages.leave"))


@bp.post("/leave/<id>/review")
def leave_review(id):
    if c.auth.me().get("role") != "admin":
        abort(403)
    status = request.form.get("status")
    if status not in ("approved", "rejected"):
        abort(400)
    E["LeaveRequest"].update(id, {"status": status})
    return redirect(url_for("pages.leave"))


# --- Timesheet -------------------------------------------------------------
@bp.get("/timesheet")
def timesheet():
    who = request.args.get("employee", "")
    employees_ = E["Employee"].list()
    rows = [e for e in E["TimeEntry"].list() if not who or e["employee_id"] == who]
    rows.sort(key=lambda e: e["clock_in"], reverse=True)
    return render_template(
        "timesheet.html", employee_options=_employee_options(employees_, "All employees"), names=_names(employees_), rows=rows, who=who)


# --- Reports ---------------------------------------------------------------
@bp.get("/reports")
def reports():
    entries, employees_ = E["TimeEntry"].list(), E["Employee"].list()
    cap = _setting(_settings(), "overtime_threshold_hours")
    rows = []
    for e in employees_:
        mine = [x for x in entries if x["employee_id"] == e["id"]]
        total = sum(hours(x) for x in mine)
        rows.append((e["full_name"], len({x.get("date") for x in mine}), total, max(0, total - cap)))
    return render_template("reports.html", rows=rows)


# --- Alerts ----------------------------------------------------------------
@bp.get("/alerts")
def alerts():
    return render_template("alerts.html", alerts=list(reversed(E["Alert"].list())))


@bp.post("/alerts/<id>/read")
def alert_read(id):
    AlertService.mark_read(id)
    return redirect(url_for("pages.alerts"))


# --- WhatsApp --------------------------------------------------------------
# Stores the connection settings and builds click-to-chat links. Sending automated
# messages needs the WhatsApp Business Cloud API on a server; keep tokens out of the browser.
@bp.route("/whatsapp", methods=["GET", "POST"])
def whatsapp():
    existing = _settings()
    if request.method == "POST":
        data = {
            "whatsapp_enabled": request.form.get("whatsapp_enabled") == "on",
            "whatsapp_number": request.form.get("whatsapp_number", ""),
        }
        if existing.get("id"):
            E["CompanySettings"].update(existing["id"], data)
        else:
            E["CompanySettings"].create(data)
        AlertService.create("system", "WhatsApp settings updated")
        return redirect(url_for("pages.whatsapp"))
    number = existing.get("whatsapp_number") or ""
    digits = "".join(ch for ch in number if ch.isdigit())
    link = f"https://wa.me/{digits}?text={quote('Test message from the time clock app', safe=chr(33) + chr(39) + '()*')}"
    return render_template("whatsapp.html", s=existing, link=link if number else None)


# --- Settings --------------------------------------------------------------
NUMERIC_SETTINGS = (
    "standard_hours_per_day",
    "overtime_threshold_hours",
    "annual_leave_days",
    "sick_leave_days",
    "late_grace_minutes",
)


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    existing = _settings()
    if request.method == "POST":
        data = {"company_name": request.form.get("company_name", "")}
        data.update({k: num(request.form.get(k)) for k in NUMERIC_SETTINGS})
        if existing.get("id"):
            E["CompanySettings"].update(existing["id"], data)
        else:
            E["CompanySettings"].create(data)
        return redirect(url_for("pages.settings", saved=1))
    return render_template("settings.html", f={**SETTINGS_DEFAULTS, **existing}, saved=request.args.get("saved"))


# --- My profile ------------------------------------------------------------
@bp.get("/profile")
def profile():
    me = c.auth.me()
    clock.sync()
    total = sum(hours(e) for e in E["TimeEntry"].list() if e["employee_id"] == me["id"])
    return render_template("profile.html", me=me, total=total, open_entry=clock.open_entry(me["id"]))
