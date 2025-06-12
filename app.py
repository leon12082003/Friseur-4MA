
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
from config import calendar_ids

app = Flask(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "/etc/secrets/credentials.json")

def get_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds)

def get_calendar_id(friseur_name):
    return calendar_ids.get(friseur_name)

@app.route("/check_availability", methods=["POST"])
def check_availability():
    data = request.json
    friseur = data.get("friseur")
    date = data.get("date")
    time = data.get("time")
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"})

    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=30)
    service = get_service()
    events = service.events().list(
        calendarId=calendar_id,
        timeMin=start_dt.isoformat() + "+02:00",
        timeMax=end_dt.isoformat() + "+02:00",
        singleEvents=True
    ).execute()
    is_free = not events.get("items")
    return jsonify({"success": True, "available": is_free})

@app.route("/free_slots_by_date", methods=["POST"])
def free_slots_by_date():
    data = request.json
    friseur = data.get("friseur")
    date = data.get("date")
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"})

    start_dt = datetime.strptime(date, "%Y-%m-%d")
    free_slots = []
    service = get_service()
    for hour in range(9, 18):
        for minute in [0, 30]:
            current = start_dt.replace(hour=hour, minute=minute)
            end = current + timedelta(minutes=30)
            events = service.events().list(
                calendarId=calendar_id,
                timeMin=current.isoformat() + "+02:00",
                timeMax=end.isoformat() + "+02:00",
                singleEvents=True
            ).execute()
            if not events.get("items"):
                free_slots.append(current.strftime("%H:%M"))
    return jsonify({"success": True, "slots": free_slots})

@app.route("/next_free_slots", methods=["POST"])
def next_free_slots():
    data = request.json
    friseur = data.get("friseur")
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"})

    now = datetime.now()
    service = get_service()
    slots = []
    current = now
    while len(slots) < 3:
        if current.hour >= 9 and current.hour < 18:
            end = current + timedelta(minutes=30)
            events = service.events().list(
                calendarId=calendar_id,
                timeMin=current.isoformat() + "+02:00",
                timeMax=end.isoformat() + "+02:00",
                singleEvents=True
            ).execute()
            if not events.get("items"):
                slots.append(current.strftime("%Y-%m-%d %H:%M"))
        current += timedelta(minutes=30)
    return jsonify({"success": True, "next_slots": slots})

@app.route("/book", methods=["POST"])
def book():
    data = request.json
    friseur = data.get("friseur")
    date = data.get("date")
    time = data.get("time")
    name = data.get("name")
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"})

    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=30)
    service = get_service()

    events = service.events().list(
        calendarId=calendar_id,
        timeMin=start_dt.isoformat() + "+02:00",
        timeMax=end_dt.isoformat() + "+02:00",
        singleEvents=True
    ).execute()
    if events.get("items"):
        return jsonify({"success": False, "message": "Termin bereits vergeben"})

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
    friseur = data.get("friseur")
    date = data.get("date")
    time = data.get("time")
    name = data.get("name")
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"})

    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=30)
    service = get_service()
    events = service.events().list(
        calendarId=calendar_id,
        timeMin=start_dt.isoformat() + "+02:00",
        timeMax=end_dt.isoformat() + "+02:00",
        singleEvents=True
    ).execute()

    found = False
    for event in events.get("items", []):
        if name.lower() in event.get("summary", "").lower():
            service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
            found = True

    if not found:
        return jsonify({"success": False, "message": "Kein passender Termin gefunden"})

    return jsonify({"success": True})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
