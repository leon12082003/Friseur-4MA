
from flask import Flask, request, jsonify
from datetime import datetime
import os
from config import calendar_ids, OPENING_HOURS
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'credentials.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

def get_calendar_service():
    return build('calendar', 'v3', credentials=credentials)

def find_calendar_id(friseur_name):
    return calendar_ids.get(friseur_name)

@app.route("/check_availability", methods=["POST"])
def check_availability():
    try:
        data = request.get_json()
        friseur = data.get("friseur")
        date = data.get("date")
        time = data.get("time")

        calendar_id = find_calendar_id(friseur)
        if not calendar_id:
            return jsonify({"message": "Friseur nicht gefunden", "success": False}), 400

        dt_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        dt_end = dt_start.replace(minute=dt_start.minute + 30)
        time_min = dt_start.isoformat() + "Z"
        time_max = dt_end.isoformat() + "Z"

        service = get_calendar_service()
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True
        ).execute()

        is_available = len(events.get("items", [])) == 0

        return jsonify({"available": is_available, "success": True})
    except Exception:
        return jsonify({"message": "Interner Fehler", "success": False}), 500

@app.route("/free_slots_by_date", methods=["POST"])
def free_slots_by_date():
    try:
        data = request.get_json()
        friseur = data.get("friseur")
        date = data.get("date")
        calendar_id = find_calendar_id(friseur)
        if not calendar_id:
            return jsonify({"message": "Friseur nicht gefunden", "success": False}), 400

        day_start = datetime.strptime(date, "%Y-%m-%d")
        free_slots = []
        service = get_calendar_service()

        for hour in range(9, 18):
            time_min = day_start.replace(hour=hour, minute=0).isoformat() + "Z"
            time_max = day_start.replace(hour=hour, minute=30).isoformat() + "Z"
            events = service.events().list(calendarId=calendar_id, timeMin=time_min, timeMax=time_max, singleEvents=True).execute()
            if not events.get("items"):
                free_slots.append(f"{hour:02d}:00")

        return jsonify({"slots": free_slots, "success": True})
    except Exception:
        return jsonify({"message": "Interner Fehler", "success": False}), 500

@app.route("/next_free_slots", methods=["POST"])
def next_free_slots():
    try:
        data = request.get_json()
        friseur = data.get("friseur")
        calendar_id = find_calendar_id(friseur)
        if not calendar_id:
            return jsonify({"message": "Friseur nicht gefunden", "success": False}), 400

        now = datetime.utcnow().isoformat() + "Z"
        service = get_calendar_service()
        events_result = service.events().list(calendarId=calendar_id, timeMin=now, maxResults=5, singleEvents=True, orderBy="startTime").execute()
        events = events_result.get("items", [])

        free_times = []
        for i in range(9, 18):
            potential_time = datetime.utcnow().replace(hour=i, minute=0)
            potential_str = potential_time.isoformat() + "Z"
            overlap = any(datetime.strptime(e["start"]["dateTime"], "%Y-%m-%dT%H:%M:%S%z").hour == i for e in events if "start" in e and "dateTime" in e["start"])
            if not overlap:
                free_times.append(f"{i:02d}:00")
            if len(free_times) == 3:
                break

        return jsonify({"next_slots": free_times, "success": True})
    except Exception:
        return jsonify({"message": "Interner Fehler", "success": False}), 500

@app.route("/book", methods=["POST"])
def book_appointment():
    try:
        data = request.get_json()
        friseur = data.get("friseur")
        date = data.get("date")
        time = data.get("time")
        name = data.get("name")

        calendar_id = find_calendar_id(friseur)
        if not calendar_id:
            return jsonify({"message": "Friseur nicht gefunden", "success": False}), 400

        dt_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        dt_end = dt_start.replace(minute=dt_start.minute + 30)
        time_min = dt_start.isoformat() + "Z"
        time_max = dt_end.isoformat() + "Z"

        service = get_calendar_service()
        existing = service.events().list(calendarId=calendar_id, timeMin=time_min, timeMax=time_max, singleEvents=True).execute()
        if existing.get("items"):
            return jsonify({"message": "Termin bereits vergeben", "success": False}), 400

        event = {
            "summary": name,
            "start": {"dateTime": time_min, "timeZone": "Europe/Berlin"},
            "end": {"dateTime": time_max, "timeZone": "Europe/Berlin"},
        }
        service.events().insert(calendarId=calendar_id, body=event).execute()
        return jsonify({"success": True})
    except Exception:
        return jsonify({"message": "Interner Fehler", "success": False}), 500

@app.route("/cancel", methods=["POST"])
def cancel_appointment():
    try:
        data = request.get_json()
        friseur = data.get("friseur")
        date = data.get("date")
        time = data.get("time")
        name = data.get("name")

        calendar_id = find_calendar_id(friseur)
        if not calendar_id:
            return jsonify({"message": "Friseur nicht gefunden", "success": False}), 400

        dt_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        dt_end = dt_start.replace(minute=dt_start.minute + 30)
        time_min = dt_start.isoformat() + "Z"
        time_max = dt_end.isoformat() + "Z"

        service = get_calendar_service()
        events = service.events().list(calendarId=calendar_id, timeMin=time_min, timeMax=time_max, singleEvents=True).execute()

        deleted = False
        for event in events.get("items", []):
            if event.get("summary") == name:
                service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
                deleted = True

        if not deleted:
            return jsonify({"message": "Kein passender Termin gefunden", "success": False}), 400

        return jsonify({"success": True})
    except Exception:
        return jsonify({"message": "Interner Fehler", "success": False}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
