"""Ntuthuko time clock - Streamlit front end (same core as the Flask version)."""
import calendar
from datetime import date, time
from urllib.parse import quote

import streamlit as st

from ntuthuko import clock
from ntuthuko.client import ntuthuko_client as c
from ntuthuko.logic import employee_names, get_settings, setting, team_availability
from ntuthuko.models import EMPLOYEE_STATUSES, LEAVE_TYPES, SETTINGS_DEFAULTS
from ntuthuko.services.alerts import AlertService
from ntuthuko.ui import hours, localdatetime, localtime, num, today

st.set_page_config(page_title="Ntuthuko", layout="wide")
E = c.entities
PAGES = ["Dashboard", "Employees", "Shifts", "Leave", "Timesheet", "Reports", "Alerts", "WhatsApp", "Settings", "My profile"]


def clock_widget(me, key):
    clock.sync()
    open_ = clock.open_entry(me["id"])
    with st.container(border=True):
        left, right = st.columns([3, 1])
        left.write(f"Clocked in since {localtime(open_['clock_in'])}" if open_ else "Not clocked in")
        if right.button("Clock out" if open_ else "Clock in", key=key):
            clock.punch("out" if open_ else "in", me["id"])
            st.rerun()


# --- pages -------------------------------------------------------------------
def dashboard(me):
    st.title("Dashboard")
    clock_widget(me, "clock_dash")
    employees, entries = E["Employee"].list(), E["TimeEntry"].list()
    leave, alerts = E["LeaveRequest"].list(), E["Alert"].list()
    names = employee_names(employees)
    active = [e for e in entries if not e.get("clock_out")]

    cols = st.columns(4)
    cols[0].metric("Employees", len(employees))
    cols[1].metric("Clocked in", len(active))
    cols[2].metric("Pending leave", sum(1 for l in leave if l.get("status") == "pending"))
    cols[3].metric("Unread alerts", sum(1 for a in alerts if not a.get("read")))

    left, right = st.columns(2)
    with left.container(border=True):
        st.subheader("Clocked in now")
        if not active:
            st.caption("Nobody is clocked in.")
        for e in active:
            st.write(f"{names.get(e['employee_id'], 'Unknown')} since {localtime(e['clock_in'])}")
    with right.container(border=True):
        st.subheader("Recent activity")
        recent = sorted(entries, key=lambda e: e["clock_in"], reverse=True)[:8]
        if not recent:
            st.caption("No time entries yet.")
        for e in recent:
            state = "clocked out" if e.get("clock_out") else "clocked in"
            st.write(f"{names.get(e['employee_id'], 'Unknown')}: {state} at {localdatetime(e.get('clock_out') or e['clock_in'])}")
    with st.container(border=True):
        st.subheader("Team availability")
        for name, label, _ in team_availability(employees, entries, leave):
            a, b = st.columns([3, 1])
            a.write(name)
            b.write(label)


def employees_page(me):
    st.title("Employees")
    items = E["Employee"].list()
    edit = st.session_state.get("emp_edit")  # None | "new" | employee id
    if edit is None:
        if st.button("Add employee"):
            st.session_state.emp_edit = "new"
            st.rerun()
    else:
        initial = {} if edit == "new" else next((e for e in items if e["id"] == edit), {})
        with st.form(f"emp_form_{edit}"):
            full_name = st.text_input("Full name", initial.get("full_name", ""))
            email = st.text_input("Email", initial.get("email", ""))
            phone = st.text_input("Phone", initial.get("phone", ""))
            role = st.text_input("Role", initial.get("role", ""))
            department = st.text_input("Department", initial.get("department", ""))
            rate = st.number_input("Hourly rate", min_value=0.0, value=float(initial.get("hourly_rate") or 0), step=1.0)
            status = st.selectbox("Status", EMPLOYEE_STATUSES, index=EMPLOYEE_STATUSES.index(initial.get("status", "active")))
            save, cancel = st.columns([1, 6])
            saved, cancelled = save.form_submit_button("Save employee"), cancel.form_submit_button("Cancel")
        if cancelled:
            st.session_state.emp_edit = None
            st.rerun()
        if saved:
            if not full_name.strip() or not email.strip():
                st.error("Full name and email are required.")
            else:
                data = {"full_name": full_name.strip(), "email": email.strip(), "phone": phone, "role": role,
                        "department": department, "hourly_rate": num(rate), "status": status}
                if initial.get("id"):
                    E["Employee"].update(initial["id"], data)
                else:
                    E["Employee"].create(data)
                st.session_state.emp_edit = None
                st.rerun()

    if not items:
        st.caption("No employees yet. Add your first one.")
    for row in range(0, len(items), 3):
        for col, e in zip(st.columns(3), items[row:row + 3]):
            with col.container(border=True):
                st.markdown(f"**{e['full_name']}**")
                st.caption(f"{e.get('role', '')}{' - ' + e['department'] if e.get('department') else ''}")
                st.caption(f"{e.get('email', '')} {e.get('phone', '')}")
                b1, b2 = st.columns(2)
                if b1.button("Edit", key=f"edit_{e['id']}"):
                    st.session_state.emp_edit = e["id"]
                    st.rerun()
                if b2.button("Delete", key=f"del_{e['id']}"):
                    E["Employee"].delete(e["id"])
                    st.rerun()


def shifts_page(me):
    st.title("Shifts")
    employees = E["Employee"].list()
    names = employee_names(employees)
    with st.form("shift_form", clear_on_submit=True):
        emp_id = st.selectbox("Employee", [""] + [e["id"] for e in employees],
                              format_func=lambda i: names.get(i, "Select employee"))
        d = st.date_input("Date", date.fromisoformat(today()))
        start = st.time_input("Start", time(8, 0))
        end = st.time_input("End", time(17, 0))
        notes = st.text_input("Notes")
        submitted = st.form_submit_button("Create shift")
    if submitted:
        if not emp_id:
            st.error("Select an employee.")
        else:
            E["Shift"].create({"employee_id": emp_id, "date": d.isoformat(), "start_time": start.strftime("%H:%M"),
                               "end_time": end.strftime("%H:%M"), "notes": notes})
            st.rerun()
    for s in sorted(E["Shift"].list(), key=lambda s: s["date"]):
        with st.container(border=True):
            a, b = st.columns([6, 1])
            a.write(f"{s['date']} {s['start_time']}-{s['end_time']}: {names.get(s['employee_id'], '')}")
            if b.button("Delete", key=f"shift_{s['id']}"):
                E["Shift"].delete(s["id"])
                st.rerun()


def leave_page(me):
    st.title("Leave")
    reqs, employees = E["LeaveRequest"].list(), E["Employee"].list()
    settings = get_settings()
    is_admin = me.get("role") == "admin"
    mine = [r for r in reqs if r["employee_id"] == me["id"]]

    def used(t):
        return sum(r.get("days") or 0 for r in mine if r.get("leave_type") == t and r.get("status") == "approved")

    left, right = st.columns(2)
    with left.container(border=True):
        st.subheader("Leave balance")
        for label, t, key in (("Annual", "annual", "annual_leave_days"), ("Sick", "sick", "sick_leave_days")):
            total = setting(settings, key)
            st.write(f"{label}: {total - used(t)} of {total} days left")
    with right.form("leave_form", clear_on_submit=True):
        leave_type = st.selectbox("Leave type", LEAVE_TYPES)
        start = st.date_input("From", date.fromisoformat(today()))
        end = st.date_input("To", date.fromisoformat(today()))
        reason = st.text_input("Reason")
        submitted = st.form_submit_button("Request leave")
    if submitted:
        days = (end - start).days + 1
        if days < 1:
            st.error("The end date must be on or after the start date.")
        else:
            E["LeaveRequest"].create({"leave_type": leave_type, "start_date": start.isoformat(),
                                      "end_date": end.isoformat(), "reason": reason, "days": days,
                                      "employee_id": me["id"], "status": "pending"})
            st.rerun()

    t = date.today()
    n = calendar.monthrange(t.year, t.month)[1]
    with st.container(border=True):
        st.subheader(t.strftime("%B %Y"))
        for row in range(1, n + 1, 7):
            for col, d in zip(st.columns(7), range(row, min(row + 7, n + 1))):
                iso = f"{t.year}-{t.month:02d}-{d:02d}"
                off = sum(1 for r in reqs if r.get("status") == "approved" and r["start_date"] <= iso <= r["end_date"])
                col.markdown(f"**{d}**" + (f"  \n:orange[{off} off]" if off else ""))

    st.subheader("All requests" if is_admin else "My requests")
    by_id = {e["id"]: e for e in employees}
    for r in (reqs if is_admin else mine):
        who = by_id.get(r["employee_id"], me)
        with st.container(border=True):
            a, b, c2 = st.columns([6, 1, 1])
            a.markdown(f"**{who.get('full_name')} - {r['leave_type']} ({r['days']} days)**  \n"
                       f"{r['start_date']} to {r['end_date']} - {r['status']}" + (f"  \n{r['reason']}" if r.get("reason") else ""))
            if is_admin and r.get("status") == "pending":
                if b.button("Approve", key=f"ok_{r['id']}"):
                    E["LeaveRequest"].update(r["id"], {"status": "approved"})
                    st.rerun()
                if c2.button("Reject", key=f"no_{r['id']}"):
                    E["LeaveRequest"].update(r["id"], {"status": "rejected"})
                    st.rerun()


def timesheet_page(me):
    st.title("Timesheet")
    employees = E["Employee"].list()
    names = employee_names(employees)
    who = st.selectbox("Employee", [""] + [e["id"] for e in employees], format_func=lambda i: names.get(i, "All employees"))
    rows = sorted((e for e in E["TimeEntry"].list() if not who or e["employee_id"] == who),
                  key=lambda e: e["clock_in"], reverse=True)
    st.dataframe(
        [{"Employee": names.get(e["employee_id"], ""), "Date": e.get("date"), "In": localtime(e["clock_in"]),
          "Out": localtime(e["clock_out"]) if e.get("clock_out") else "Still in", "Hours": round(hours(e), 2)} for e in rows],
        hide_index=True,
    )


def reports_page(me):
    st.title("Reports")
    entries, employees = E["TimeEntry"].list(), E["Employee"].list()
    cap = setting(get_settings(), "overtime_threshold_hours")
    rows = []
    for e in employees:
        mine = [x for x in entries if x["employee_id"] == e["id"]]
        total = sum(hours(x) for x in mine)
        rows.append({"Employee": e["full_name"], "Days worked": len({x.get("date") for x in mine}),
                     "Total hours": round(total, 1), "Overtime hours": round(max(0, total - cap), 1)})
    if rows:
        st.dataframe(rows, hide_index=True)
    else:
        st.caption("Add employees and time entries to see reports.")


def alerts_page(me):
    st.title("Alerts")
    alerts = list(reversed(E["Alert"].list()))
    if not alerts:
        st.caption("You have no alerts.")
    for a in alerts:
        with st.container(border=True):
            left, right = st.columns([6, 1])
            left.write(a["message"])
            left.caption(f"{a['type']} - {localdatetime(a.get('created_date'))}" + ("" if not a.get("read") else " (read)"))
            if not a.get("read") and right.button("Mark as read", key=f"read_{a['id']}"):
                AlertService.mark_read(a["id"])
                st.rerun()


def whatsapp_page(me):
    st.title("WhatsApp")
    existing = get_settings()
    with st.form("wa_form"):
        enabled = st.checkbox("Enable WhatsApp notifications", value=bool(existing.get("whatsapp_enabled")))
        number = st.text_input("Business number (with country code, e.g. 27821234567)", existing.get("whatsapp_number", ""))
        submitted = st.form_submit_button("Save WhatsApp settings")
    if submitted:
        data = {"whatsapp_enabled": enabled, "whatsapp_number": number}
        if existing.get("id"):
            E["CompanySettings"].update(existing["id"], data)
        else:
            E["CompanySettings"].create(data)
        AlertService.create("system", "WhatsApp settings updated")
        st.rerun()
    saved = existing.get("whatsapp_number")
    if saved:
        digits = "".join(ch for ch in saved if ch.isdigit())
        st.link_button("Open test chat", f"https://wa.me/{digits}?text={quote('Test message from the time clock app')}")


def settings_page(me):
    st.title("Settings")
    existing = get_settings()
    f = {**SETTINGS_DEFAULTS, **existing}
    labels = {"standard_hours_per_day": "Standard hours per day", "overtime_threshold_hours": "Overtime after (hours per week)",
              "annual_leave_days": "Annual leave days", "sick_leave_days": "Sick leave days", "late_grace_minutes": "Late grace (minutes)"}
    with st.form("settings_form"):
        company = st.text_input("Company name", f["company_name"])
        values = {k: st.number_input(lbl, value=float(f[k]), step=1.0, format="%g") for k, lbl in labels.items()}
        submitted = st.form_submit_button("Save settings")
    if submitted:
        data = {"company_name": company, **{k: num(v) for k, v in values.items()}}
        if existing.get("id"):
            E["CompanySettings"].update(existing["id"], data)
        else:
            E["CompanySettings"].create(data)
        st.success("Saved")


def profile_page(me):
    st.title("My profile")
    total = sum(hours(e) for e in E["TimeEntry"].list() if e["employee_id"] == me["id"])
    with st.container(border=True):
        st.markdown(f"**{me['full_name']}**")
        st.caption(f"{me['email']} - {me['role']}")
        st.write(f"Total hours logged: {total:.1f}")
    clock_widget(me, "clock_profile")


ROUTES = {"Dashboard": dashboard, "Employees": employees_page, "Shifts": shifts_page, "Leave": leave_page,
          "Timesheet": timesheet_page, "Reports": reports_page, "Alerts": alerts_page, "WhatsApp": whatsapp_page,
          "Settings": settings_page, "My profile": profile_page}

page = st.sidebar.radio("Navigate", PAGES, label_visibility="collapsed")
ROUTES[page](c.auth.me())
