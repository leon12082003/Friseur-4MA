from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import os
from config import CALENDARS, OPENING_HOURS

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

def get_service():
    return build('calendar', 'v3', credentials=credentials)

def get_calendar_id(friseur_name):
    return CALENDARS.get(friseur_name)

def is_within_opening_hours(date_str, time_str):
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    day = dt.strftime("%a")
    if day not in OPENING_HOURS:
        return False
    start, end = OPENING_HOURS[day]
    return start <= time_str < end

@app.route("/check_availability", methods=["POST"])
def check_availability():
    data = request.json
    friseur = data["friseur"]
    date = data["date"]
    time = data["time"]
    calendar_id = get_calendar_id(friseur)
    if not calendar_id or not is_within_opening_hours(date, time):
        return jsonify({"available": False})

    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=30)

    service = get_service()
    events = service.events().list(
        calendarId=calendar_id,
        timeMin=start_dt.isoformat() + "+02:00",
        timeMax=end_dt.isoformat() + "+02:00",
        singleEvents=True
    ).execute()

    available = len(events.get('items', [])) == 0
    return jsonify({"available": available})

@app.route("/free_slots_by_date", methods=["POST"])
def free_slots_by_date():
    data = request.json
    friseur = data["friseur"]
    date = data["date"]
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify([])

    service = get_service()
    day_start = datetime.strptime(date + " 09:00", "%Y-%m-%d %H:%M")
    slots = []
    for i in range(18):
        slot_start = day_start + timedelta(minutes=30 * i)
        time_str = slot_start.strftime("%H:%M")
        if not is_within_opening_hours(date, time_str):
            continue
        slot_end = slot_start + timedelta(minutes=30)
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=slot_start.isoformat() + "+02:00",
            timeMax=slot_end.isoformat() + "+02:00",
            singleEvents=True
        ).execute()
        if len(events.get("items", [])) == 0:
            slots.append(time_str)
    return jsonify({"free_slots": slots})

@app.route("/next_free_slots", methods=["POST"])
def next_free_slots():
    data = request.json
    friseur = data["friseur"]
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify([])

    service = get_service()
    now = datetime.now().astimezone()
    found = []
    dt = now.replace(minute=0, second=0, microsecond=0)

    while len(found) < 3:
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M")
        if is_within_opening_hours(date_str, time_str):
            end = dt + timedelta(minutes=30)
            events = service.events().list(
                calendarId=calendar_id,
                timeMin=dt.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True
            ).execute()
            if len(events.get("items", [])) == 0:
                found.append({"date": date_str, "time": time_str})
        dt += timedelta(minutes=30)
    return jsonify({"next_slots": found})

@app.route("/book", methods=["POST"])
def book():
    data = request.json
    friseur = data["friseur"]
    date = data["date"]
    time = data["time"]
    name = data["name"]
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"success": False})

    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=30)

    service = get_service()
    event = {
        "summary": f"Termin: {name}",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Berlin"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Berlin"},
    }

    service.events().insert(calendarId=calendar_id, body=event).execute()
    return jsonify({"success": True})

@app.route("/cancel", methods=["POST"])
def cancel():
    data = request.json
    friseur = data["friseur"]
    date = data["date"]
    time = data["time"]
    name = data["name"]
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"success": False})

    service = get_service()
    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=30)

    events = service.events().list(
        calendarId=calendar_id,
        timeMin=start_dt.isoformat() + "+02:00",
        timeMax=end_dt.isoformat() + "+02:00",
        q=name,
        singleEvents=True
    ).execute()

    for event in events.get("items", []):
        service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()

    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)
