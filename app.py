from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import calendar_ids

app = Flask(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
SERVICE_ACCOUNT_FILE = "credentials.json"

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
service = build("calendar", "v3", credentials=credentials)

def get_calendar_id(friseur):
    return calendar_ids.get(friseur)

@app.route("/check_availability", methods=["POST"])
def check_availability():
    data = request.get_json()
    friseur = data.get("friseur")
    date = data.get("date")
    time = data.get("time")
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"message": "Friseur nicht gefunden", "success": False}), 400
    try:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=30)
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=start_dt.isoformat() + "Z",
            timeMax=end_dt.isoformat() + "Z",
            singleEvents=True
        ).execute()
        if events.get("items"):
            return jsonify({"message": "Termin bereits vergeben", "success": False}), 200
        return jsonify({"success": True}), 200
    except Exception:
        return jsonify({"message": "Interner Fehler", "success": False}), 500

@app.route("/free_slots_by_date", methods=["POST"])
def free_slots_by_date():
    data = request.get_json()
    friseur = data.get("friseur")
    date = data.get("date")
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify([])
    start_of_day = datetime.strptime(date + " 09:00", "%Y-%m-%d %H:%M")
    end_of_day = datetime.strptime(date + " 18:00", "%Y-%m-%d %H:%M")
    slots = [(start_of_day + timedelta(minutes=30*i)).strftime("%H:%M") for i in range(int((end_of_day-start_of_day).seconds / 1800))]
    events = service.events().list(calendarId=calendar_id, timeMin=start_of_day.isoformat() + "Z", timeMax=end_of_day.isoformat() + "Z", singleEvents=True).execute()
    booked = [datetime.fromisoformat(e["start"]["dateTime"]).strftime("%H:%M") for e in events.get("items", [])]
    return jsonify([s for s in slots if s not in booked])

@app.route("/next_free_slots", methods=["POST"])
def next_free_slots():
    data = request.get_json()
    friseur = data.get("friseur")
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify([])
    now = datetime.utcnow()
    slots = []
    for i in range(30):
        day = now + timedelta(days=i)
        if day.weekday() >= 6:
            continue
        for h in range(9, 18):
            for m in (0, 30):
                start = day.replace(hour=h, minute=m, second=0, microsecond=0)
                end = start + timedelta(minutes=30)
                events = service.events().list(calendarId=calendar_id, timeMin=start.isoformat() + "Z", timeMax=end.isoformat() + "Z", singleEvents=True).execute()
                if not events.get("items"):
                    slots.append({"date": start.strftime("%Y-%m-%d"), "time": start.strftime("%H:%M")})
                if len(slots) >= 3:
                    return jsonify(slots)
    return jsonify(slots)

@app.route("/book", methods=["POST"])
def book():
    data = request.get_json()
    friseur = data.get("friseur")
    date = data.get("date")
    time = data.get("time")
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"message": "Friseur nicht gefunden", "success": False}), 400
    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=30)
    events = service.events().list(calendarId=calendar_id, timeMin=start_dt.isoformat() + "Z", timeMax=end_dt.isoformat() + "Z", singleEvents=True).execute()
    if events.get("items"):
        return jsonify({"message": "Termin bereits vergeben", "success": False}), 200
    service.events().insert(calendarId=calendar_id, body={
        "summary": "Friseurtermin",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Berlin"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Berlin"}
    }).execute()
    return jsonify({"success": True})

@app.route("/cancel", methods=["POST"])
def cancel():
    data = request.get_json()
    friseur = data.get("friseur")
    date = data.get("date")
    time = data.get("time")
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"message": "Friseur nicht gefunden", "success": False}), 400
    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=30)
    events = service.events().list(calendarId=calendar_id, timeMin=start_dt.isoformat() + "Z", timeMax=end_dt.isoformat() + "Z", singleEvents=True).execute()
    found = False
    for e in events.get("items", []):
        service.events().delete(calendarId=calendar_id, eventId=e["id"]).execute()
        found = True
    if not found:
        return jsonify({"message": "Kein passender Termin gefunden", "success": False}), 200
    return jsonify({"success": True})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
