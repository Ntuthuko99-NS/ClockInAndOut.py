import re
import tempfile
import unittest
from pathlib import Path

from ntuthuko import create_app
from ntuthuko import clock
from ntuthuko.client import ntuthuko_client as c
from ntuthuko.services.alerts import AlertService
from ntuthuko.ui import hours, num


class AppTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        app = create_app(self.tmp_path / "data.json")
        app.testing = True
        self.client = app.test_client()

    def test_every_page_renders_empty(self):
        client = self.client
        for path in ["/", "/employees", "/shifts", "/leave", "/timesheet", "/reports", "/alerts",
                     "/whatsapp", "/settings", "/profile", "/employees?edit=new"]:
            r = client.get(path)
            assert r.status_code == 200, path
        assert b"No employees yet" in client.get("/employees").data
        assert b"You have no alerts." in client.get("/alerts").data
        assert b"Add employees and time entries" in client.get("/reports").data
        assert b"Not clocked in" in client.get("/").data

    def test_employee_crud(self):
        client = self.client
        client.post("/employees/save", data={"full_name": "Thandi Nkosi", "email": "t@x.co", "hourly_rate": "120.5", "role": "Cashier"})
        emp = c.entities["Employee"].list()[0]
        assert emp["hourly_rate"] == 120.5 and emp["status"] == "active"
        assert b"Thandi Nkosi" in client.get("/employees").data
        # edit
        assert b'value="Thandi Nkosi"' in client.get(f"/employees?edit={emp['id']}").data
        client.post("/employees/save", data={"id": emp["id"], "full_name": "Thandi N", "email": "t@x.co", "status": "inactive"})
        emp = c.entities["Employee"].list()[0]
        assert emp["full_name"] == "Thandi N" and emp["status"] == "inactive"
        # validation
        client.post("/employees/save", data={"full_name": "", "email": ""})
        assert len(c.entities["Employee"].list()) == 1
        client.post(f"/employees/{emp['id']}/delete")
        assert c.entities["Employee"].list() == []

    def test_clock_in_out_and_reports(self):
        client = self.client
        client.post("/employees/save", data={"full_name": "Sipho", "email": "s@x.co"})
        emp = c.entities["Employee"].list()[0]
        # the demo user ("me") clocks in/out through the widget
        client.post("/clock", data={"next": "dashboard"})
        assert b"Clocked in since" in client.get("/").data
        assert b"Clock out" in client.get("/profile").data
        client.post("/clock", data={"next": "profile"})
        entries = c.entities["TimeEntry"].list()
        assert len(entries) == 1 and entries[0]["clock_out"] and entries[0]["date"] == entries[0]["clock_in"][:10]
        assert c.raw_get("clock_queue") == []
        assert b"Not clocked in" in client.get("/").data
        # a completed shift for Sipho: 8.5 hours
        c.entities["TimeEntry"].create({"employee_id": emp["id"], "date": "2026-10-12",
                                        "clock_in": "2026-10-12T06:00:00.000Z", "clock_out": "2026-10-12T14:30:00.000Z"})
        assert hours(c.entities["TimeEntry"].filter(employee_id=emp["id"])[0]) == 8.5
        page = client.get("/reports").data.decode()
        assert re.search(r"Sipho</td><td>1</td><td>8.5</td><td>0.0</td>", page)
        assert b"8.50" in client.get("/timesheet").data
        assert b"8.50" in client.get(f"/timesheet?employee={emp['id']}").data
        assert b"8.50" not in client.get("/timesheet?employee=nobody").data

    def test_queue_replays_after_interruption(self):
        client = self.client
        c.raw_set("clock_queue", [{"type": "in", "employee_id": "me", "time": "2026-10-13T08:00:00.000Z"}])
        clock.sync()
        assert c.raw_get("clock_queue") == []
        assert c.entities["TimeEntry"].list()[0]["clock_in"] == "2026-10-13T08:00:00.000Z"

    def test_overtime(self):
        client = self.client
        client.post("/employees/save", data={"full_name": "Zanele", "email": "z@x.co"})
        emp = c.entities["Employee"].list()[0]
        for day in range(1, 6):  # 5 x 9h = 45h, cap 40
            c.entities["TimeEntry"].create({"employee_id": emp["id"], "date": f"2026-10-0{day}",
                                            "clock_in": f"2026-10-0{day}T06:00:00.000Z", "clock_out": f"2026-10-0{day}T15:00:00.000Z"})
        assert re.search(r"Zanele</td><td>5</td><td>45.0</td><td>5.0</td>", client.get("/reports").data.decode())
        client.post("/settings", data={"company_name": "Acme", "overtime_threshold_hours": "50"})
        assert re.search(r"Zanele</td><td>5</td><td>45.0</td><td>0.0</td>", client.get("/reports").data.decode())

    def test_shifts(self):
        client = self.client
        client.post("/employees/save", data={"full_name": "Lerato", "email": "l@x.co"})
        emp = c.entities["Employee"].list()[0]
        client.post("/shifts", data={"employee_id": "", "date": "2026-10-20"})  # rejected
        assert c.entities["Shift"].list() == []
        client.post("/shifts", data={"employee_id": emp["id"], "date": "2026-10-21", "start_time": "09:00", "end_time": "17:00"})
        client.post("/shifts", data={"employee_id": emp["id"], "date": "2026-10-20", "start_time": "08:00", "end_time": "16:00"})
        page = client.get("/shifts").data.decode()
        assert page.index("2026-10-20") < page.index("2026-10-21")  # sorted by date
        assert "08:00-16:00: Lerato" in page
        client.post(f"/shifts/{c.entities['Shift'].list()[0]['id']}/delete")
        assert len(c.entities["Shift"].list()) == 1

    def test_leave_flow(self):
        client = self.client
        client.post("/leave", data={"leave_type": "annual", "start_date": "2026-10-13", "end_date": "2026-10-15", "reason": "Trip"})
        req = c.entities["LeaveRequest"].list()[0]
        assert req["days"] == 3 and req["status"] == "pending" and req["employee_id"] == "me"
        # invalid: end before start
        client.post("/leave", data={"leave_type": "annual", "start_date": "2026-10-15", "end_date": "2026-10-13"})
        assert len(c.entities["LeaveRequest"].list()) == 1
        page = client.get("/leave").data.decode()
        assert "Demo User - annual (3 days)" in page and "15 of 15 days left" in page and "Approve" in page
        client.post(f"/leave/{req['id']}/review", data={"status": "approved"})
        page = client.get("/leave").data.decode()
        assert "12 of 15 days left" in page and "30 of 30 days left" in page
        assert b"Approve" not in client.get("/leave").data
        assert client.post(f"/leave/{req['id']}/review", data={"status": "nonsense"}).status_code == 400

    def test_non_admin_cannot_review(self):
        client = self.client
        c.raw_set("me", {"id": "e1", "full_name": "Staff", "email": "s@x.co", "role": "staff"})
        req = c.entities["LeaveRequest"].create({"employee_id": "e1", "leave_type": "sick", "start_date": "2026-10-13",
                                                 "end_date": "2026-10-13", "days": 1, "status": "pending"})
        assert client.post(f"/leave/{req['id']}/review", data={"status": "approved"}).status_code == 403
        assert b"My requests" in client.get("/leave").data

    def test_leave_calendar_marks_days(self):
        client = self.client
        from datetime import date
        t = date.today()
        c.entities["LeaveRequest"].create({"employee_id": "me", "leave_type": "annual", "start_date": t.isoformat(),
                                           "end_date": t.isoformat(), "days": 1, "status": "approved"})
        assert b"1 off" in client.get("/leave").data

    def test_alerts_and_whatsapp(self):
        client = self.client
        client.post("/whatsapp", data={"whatsapp_enabled": "on", "whatsapp_number": "+27 82 123 4567"})
        s = c.entities["CompanySettings"].list()[0]
        assert s["whatsapp_enabled"] is True
        page = client.get("/whatsapp").data.decode()
        assert "https://wa.me/27821234567?text=Test%20message%20from%20the%20time%20clock%20app" in page
        assert " checked" in page
        # the system alert shows up, unread, then gets marked read
        assert len(AlertService.unread()) == 1
        assert "WhatsApp settings updated" in client.get("/alerts").data.decode()
        assert b"Unread alerts" in client.get("/").data
        client.post(f"/alerts/{AlertService.unread()[0]['id']}/read")
        assert AlertService.unread() == []
        assert b"Mark as read" not in client.get("/alerts").data
        # saving again with checkbox off
        client.post("/whatsapp", data={"whatsapp_number": ""})
        assert c.entities["CompanySettings"].list()[0]["whatsapp_enabled"] is False
        assert len(c.entities["CompanySettings"].list()) == 1  # updated in place, not duplicated

    def test_settings_roundtrip(self):
        client = self.client
        assert b'value="8"' in client.get("/settings").data
        client.post("/settings", data={"company_name": "Acme", "standard_hours_per_day": "7.5", "overtime_threshold_hours": "45",
                                       "annual_leave_days": "20", "sick_leave_days": "30", "late_grace_minutes": "5"})
        assert b"Saved" in client.get("/settings?saved=1").data
        page = client.get("/settings").data.decode()
        assert 'value="Acme"' in page and 'value="7.5"' in page and 'value="45"' in page
        assert "20 of 20 days left" in client.get("/leave").data.decode()

    def test_check_late(self):
        emp = {"id": "e1", "full_name": "Late Larry"}
        shift = {"date": "2026-10-13", "start_time": "08:00"}
        from datetime import datetime, timedelta
        start = datetime.fromisoformat("2026-10-13T08:00").astimezone()
        on_time = (start + timedelta(minutes=5)).astimezone().isoformat()
        late = (start + timedelta(minutes=11)).astimezone().isoformat()
        assert AlertService.check_late(emp, shift, on_time) is None
        a = AlertService.check_late(emp, shift, late)
        assert a["type"] == "late" and a["message"] == "Late Larry clocked in late" and a["read"] is False

    def test_client_shape_and_helpers(self):
        tmp_path = self.tmp_path
        c.configure(tmp_path / "x.json")
        a = c.entities["Shift"].create({"employee_id": "e", "date": "d"})
        assert a["id"] and a["created_date"].endswith("Z")
        c.entities["Shift"].update(a["id"], {"notes": "hi"})
        assert c.entities["Shift"].filter(notes="hi", employee_id="e")[0]["date"] == "d"
        assert c.entities["Shift"].filter(notes="nope") == []
        assert c.auth.me()["role"] == "admin"
        assert [num("8"), num("7.5"), num(""), num("abc"), num(None)] == [8, 7.5, 0, 0, 0]


if __name__ == "__main__":
    unittest.main()
