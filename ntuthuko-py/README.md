# Ntuthuko time clock (Python)

Python port of the React app: employees, shifts, leave, timesheets, reports,
alerts, WhatsApp settings and a clock in/out widget. Two front ends share the
same core (`client.py`, `clock.py`, `logic.py`, `ui.py`, `services/`):

| Front end | Entry point | Install | Run |
| --------- | ----------- | ------- | --- |
| Streamlit | `streamlit_app.py` | `pip install -r requirements.txt` | `streamlit run streamlit_app.py` |
| Flask     | `run.py`           | `pip install -r requirements-flask.txt` | `python run.py` (http://127.0.0.1:5000) |

Flask tests: `python -m unittest discover -s tests`

## Deploy on Streamlit Community Cloud

1. `streamlit_app.py` and `requirements.txt` must be at the **root of the GitHub
   repo** (not inside a sub-folder), or set "Main file path" to the sub-folder
   path, e.g. `ntuthuko-py/streamlit_app.py`.
2. Repository `Ntuthuko99-NS/Ntuthuko.py`, branch `main`, main file `streamlit_app.py`.

**Know before you deploy:** data is stored in a JSON file, and Streamlit Cloud's
disk is temporary - it resets whenever the app restarts, sleeps or is
redeployed. Everyone who opens the app is the same demo admin. Use a real
database and login before relying on it, and set the app to private in its
Share settings meanwhile.

Environment variables (all optional): `NTUTHUKO_DATA` (data file, default
`ntuthuko_data.json`), `SECRET_KEY`, `APP_TZ` (e.g. `Africa/Johannesburg`;
default is the server's timezone), `HOST`, `PORT`, `FLASK_DEBUG=1`.

## Where things went

| React                                   | Python                                          |
| --------------------------------------- | ----------------------------------------------- |
| `App.jsx` routes, `Layout.js`           | Flask: `ntuthuko/__init__.py`, `pages.py`, `templates/base.html`; Streamlit: sidebar in `streamlit_app.py` |
| `pages/*.jsx`                           | Flask: `pages.py` + `templates/<page>.html`; Streamlit: one function per page in `streamlit_app.py` |
| `components/*.jsx`, `ui.jsx`            | Jinja macros in `templates/components.html`, `_ui.html`; helpers in `ui.py` |
| `api/ntuthukoClient.js`, `useEntity.js` | `client.py` (same `list/filter/create/update/delete` shape, JSON file instead of localStorage) |
| `services/AlertService.js`              | `services/alerts.py`                            |
| `components/ClockOfflineSync.js`        | `clock.py`                                      |
| `entities/*.json`                       | `models.py` (dataclasses)                       |

## Before exposing it beyond your own machine

- There is no login: `client.auth.me()` returns a demo admin (or whatever is
  stored under the `me` key). Add real authentication.
- Forms have no CSRF protection (e.g. add Flask-WTF).
- Set a real `SECRET_KEY`.
- Tailwind is loaded from its CDN; build it with the Tailwind CLI for production.
- Sending WhatsApp messages needs the WhatsApp Business Cloud API on a server.
