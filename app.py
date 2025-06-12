
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

def get_calendar_id(friseur):
    calendar_ids = {
        "Lisa Fischer": os.getenv("LISA_CALENDAR_ID"),
        "Marco Richter": os.getenv("MARCO_CALENDAR_ID"),
        "Marie Zeiser": os.getenv("MARIE_CALENDAR_ID"),
        "Max Herrmann": os.getenv("MAX_CALENDAR_ID"),
    }
    return calendar_ids.get(friseur, None)

def get_service():
    credentials_info = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=credentials)

@app.route("/check", methods=["POST"])
def check_availability():
    data = request.json
    friseur = data["friseur"]
    date = data["date"]
    time = data["time"]
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

    available = not events.get("items")
    return jsonify({"available": available})

@app.route("/slots", methods=["POST"])
def slots():
    data = request.json
    friseur = data["friseur"]
    date = data["date"]
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"})

    service = get_service()
    slots = []
    start_dt = datetime.strptime(date + " 09:00", "%Y-%m-%d")
    end_dt = datetime.strptime(date + " 18:00", "%Y-%m-%d")

    if start_dt.weekday() == 5:
        end_dt = datetime.strptime(date + " 14:00", "%Y-%m-%d")

    while start_dt < end_dt:
        end_time = start_dt + timedelta(minutes=30)
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=start_dt.isoformat() + "+02:00",
            timeMax=end_time.isoformat() + "+02:00",
            singleEvents=True
        ).execute()
        if not events.get("items"):
            slots.append(start_dt.strftime("%H:%M"))
        start_dt = end_time

    return jsonify({"slots": slots})

@app.route("/next", methods=["POST"])
def next_free():
    data = request.json
    friseur = data["friseur"]
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"})

    service = get_service()
    now = datetime.now()
    slots = []
    while len(slots) < 3:
        if now.weekday() >= 5 and now.hour >= 14:
            now += timedelta(days=1)
            now = now.replace(hour=9, minute=0)
            continue
        if now.weekday() < 5 and now.hour >= 18:
            now += timedelta(days=1)
            now = now.replace(hour=9, minute=0)
            continue

        end_time = now + timedelta(minutes=30)
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat() + "+02:00",
            timeMax=end_time.isoformat() + "+02:00",
            singleEvents=True
        ).execute()
        if not events.get("items"):
            slots.append(now.strftime("%Y-%m-%d %H:%M"))
        now += timedelta(minutes=30)

    return jsonify({"next_slots": slots})

@app.route("/book", methods=["POST"])
def book():
    data = request.json
    friseur = data["friseur"]
    date = data["date"]
    time = data["time"]
    name = data["name"]
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
    return jsonify({"success": True, "message": "Termin erfolgreich gebucht"})

@app.route("/cancel", methods=["POST"])
def cancel():
    data = request.json
    friseur = data["friseur"]
    date = data["date"]
    time = data["time"]
    name = data["name"]
    calendar_id = get_calendar_id(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"})

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

    matched = events.get("items", [])
    if not matched:
        return jsonify({"success": False, "message": "Kein passender Termin gefunden"})

    for event in matched:
        service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()

    return jsonify({"success": True, "message": "Termin erfolgreich gelöscht"})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

