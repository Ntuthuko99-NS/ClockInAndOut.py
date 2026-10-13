"""Ntuthuko time clock - Flask port of the React app (App.jsx + Layout.js)."""
import os

from .client import ntuthuko_client
from .ui import hours, localdatetime, localtime

# (path, label) - same nav as Layout.js
NAV_LINKS = [
    ("/", "Dashboard"),
    ("/employees", "Employees"),
    ("/shifts", "Shifts"),
    ("/leave", "Leave"),
    ("/timesheet", "Timesheet"),
    ("/reports", "Reports"),
    ("/alerts", "Alerts"),
    ("/whatsapp", "WhatsApp"),
    ("/settings", "Settings"),
    ("/profile", "My profile"),
]


def create_app(data_file=None):
    from flask import Flask  # imported here so the Streamlit app does not need Flask

    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
    if data_file:
        ntuthuko_client.configure(data_file)

    app.jinja_env.filters["localtime"] = localtime
    app.jinja_env.filters["localdatetime"] = localdatetime
    app.jinja_env.filters["entry_hours"] = hours
    app.jinja_env.globals["opts"] = lambda seq: [(x, x) for x in seq]

    @app.context_processor
    def inject_layout():
        return {"nav_links": NAV_LINKS}

    from .pages import bp

    app.register_blueprint(bp)
    return app
